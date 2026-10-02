"""One bounded, tool-free Claude structured-output request to the fixed official API."""

import asyncio
import copy
import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from .config import Settings

OutputT = TypeVar("OutputT", bound=BaseModel)
ENDPOINT = "https://api.anthropic.com/v1/messages"
MAX_RESPONSE_BYTES = 1_048_576
UNSUPPORTED = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
}
SUPPORTED_FORMATS = {
    "date-time",
    "time",
    "date",
    "duration",
    "email",
    "hostname",
    "uri",
    "ipv4",
    "ipv6",
    "uuid",
}


class AnthropicFailure(RuntimeError):
    """Fixed public explanations; never include provider bodies or diagnostics."""


def output_schema(output_type: type[BaseModel]) -> dict[str, Any]:
    """Simplify only our schema; validate every original constraint on the response."""
    schema = copy.deepcopy(output_type.model_json_schema())

    def transform(node: dict[str, Any]) -> None:
        removed = {key: node.pop(key) for key in sorted(UNSUPPORTED) if key in node}
        if "minItems" in node and node["minItems"] not in (0, 1):
            removed["minItems"] = node.pop("minItems")
        if "format" in node and node["format"] not in SUPPORTED_FORMATS:
            removed["format"] = node.pop("format")
        if removed:
            node["description"] = (
                node.get("description", "") + " Required constraints: " + json.dumps(removed)
            ).strip()
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
        for key in ("properties", "$defs", "definitions"):
            for child in node.get(key, {}).values():
                transform(child)
        for key in ("anyOf", "allOf", "oneOf", "prefixItems"):
            for child in node.get(key, []):
                transform(child)
        if isinstance(node.get("items"), dict):
            transform(node["items"])

    transform(schema)
    return schema


def _token_count(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10_000_000:
        raise AnthropicFailure("Claude returned invalid token usage.")
    return value


def _parse(payload: Any, output_type: type[OutputT], max_tokens: int) -> tuple[OutputT, int, int]:
    if not isinstance(payload, dict) or payload.get("stop_reason") != "end_turn":
        raise AnthropicFailure("Claude did not return a complete structured result.")
    blocks = payload.get("content")
    if (
        not isinstance(blocks, list)
        or len(blocks) != 1
        or not isinstance(blocks[0], dict)
        or blocks[0].get("type") != "text"
        or not isinstance(blocks[0].get("text"), str)
    ):
        raise AnthropicFailure("Claude returned unsupported response content.")
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise AnthropicFailure("Claude returned invalid token usage.")
    input_tokens = _token_count(usage.get("input_tokens"))
    output_tokens = _token_count(usage.get("output_tokens"))
    if output_tokens > max_tokens:
        raise AnthropicFailure("Claude returned invalid token usage.")
    data = output_type.model_validate(json.loads(blocks[0]["text"]))
    return data, input_tokens, output_tokens


async def run_anthropic(
    instructions: str,
    content: str,
    output_type: type[OutputT],
    settings: Settings,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[OutputT, int, int]:
    if settings.ai_provider != "anthropic" or not settings.llm_enabled:
        raise AnthropicFailure("Claude is not configured as the selected provider.")
    if len(content) > settings.max_input_chars:
        raise AnthropicFailure("AI input exceeds the configured limit.")
    try:
        async with (
            asyncio.timeout(settings.ai_timeout_s),
            httpx.AsyncClient(
                timeout=settings.ai_timeout_s,
                follow_redirects=False,
                trust_env=False,
                transport=transport,
            ) as client,
            client.stream(
                "POST",
                ENDPOINT,
                headers={
                    "x-api-key": settings.anthropic_api_key or "",
                    "anthropic-version": "2023-06-01",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
                json={
                    "model": settings.ai_model,
                    "max_tokens": settings.ai_max_output_tokens,
                    "system": instructions,
                    "messages": [{"role": "user", "content": content}],
                    "output_config": {
                        "format": {"type": "json_schema", "schema": output_schema(output_type)}
                    },
                },
            ) as response,
        ):
            if response.status_code != 200:
                raise AnthropicFailure("Claude request failed.")
            if response.headers.get("content-encoding", "identity").strip().lower() not in (
                "",
                "identity",
            ):
                raise AnthropicFailure("Claude returned an unsupported response encoding.")
            buffer = bytearray()
            async for chunk in response.aiter_bytes():
                if len(buffer) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise AnthropicFailure("Claude response exceeded the safe size limit.")
                buffer.extend(chunk)
            return _parse(json.loads(buffer), output_type, settings.ai_max_output_tokens)
    except (httpx.HTTPError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise AnthropicFailure("Claude returned an invalid structured result.") from exc
