"""Offline reviewed AI environment policy for existing-service release guards."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

KEY_ALIASES = {
    "JOBBR_OPENAI_API_KEY",
    "OPENAI_API_KEY",
    "JOBBR_ANTHROPIC_API_KEY",
    "ANTHROPIC_API_KEY",
}


@dataclass(frozen=True)
class AIPolicy:
    values: dict[str, str]
    secret_refs: dict[str, str]


def reviewed_ai(environ: Mapping[str, str]) -> AIPolicy:
    provider = environ.get("JOBBR_RELEASE_AI_PROVIDER", "")
    model = environ.get("JOBBR_RELEASE_AI_MODEL", "")
    reference = environ.get("JOBBR_AI_SECRET_REF", "")
    if provider == "off":
        if model or reference:
            raise SystemExit(
                "AI-off releases cannot declare a model or provider secret."
            )
        return AIPolicy({"JOBBR_AI_PROVIDER": "openai"}, {})
    if provider not in {"openai", "anthropic"}:
        raise SystemExit("Choose an explicit reviewed AI release policy.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model):
        raise SystemExit("Missing or invalid reviewed AI model.")
    if not re.fullmatch("jobbr-" + provider + r"-api-key:[1-9][0-9]*", reference):
        raise SystemExit(
            "Selected provider needs its matching numeric Jobbr secret reference."
        )
    model_variable = "JOBBR_MODEL" if provider == "openai" else "JOBBR_ANTHROPIC_MODEL"
    key_variable = (
        "JOBBR_OPENAI_API_KEY" if provider == "openai" else "JOBBR_ANTHROPIC_API_KEY"
    )
    return AIPolicy(
        {"JOBBR_AI_PROVIDER": provider, model_variable: model},
        {key_variable: reference},
    )


def verify_ai(entries: object, policy: AIPolicy) -> None:
    if not isinstance(entries, list) or any(
        not isinstance(entry, dict) for entry in entries
    ):
        raise SystemExit("AI environment is malformed; refusing release.")
    names = [entry.get("name") for entry in entries]
    if any(not isinstance(name, str) for name in names) or len(names) != len(
        set(names)
    ):
        raise SystemExit("AI environment is ambiguous; refusing release.")
    environment = {entry["name"]: entry for entry in entries}
    for name, expected in policy.values.items():
        entry = environment.get(name, {})
        if entry.get("value") != expected or "valueFrom" in entry:
            raise SystemExit(
                "AI provider/model differs from the reviewed release policy."
            )
    for name in KEY_ALIASES - policy.secret_refs.keys():
        if name in environment:
            raise SystemExit(
                "Inherited or unselected provider credentials are forbidden."
            )
    for name, reference in policy.secret_refs.items():
        entry = environment.get(name, {})
        secret = entry.get("valueFrom", {}).get("secretKeyRef", {})
        expected_name, version = reference.split(":")
        if (
            "value" in entry
            or secret.get("name") != expected_name
            or str(secret.get("key", "")) != version
        ):
            raise SystemExit(
                "AI key binding differs from the reviewed numeric secret reference."
            )
