from enum import Enum


class GenreURLChoices(Enum):
    ROCK = "rock"
    ELECTRONIC = "electronic"
    METAL = "metal"
    HIP_HOP = "hip-hop"


class GenreChoices(Enum):
    ROCK = "Rock"
    ELECTRONIC = "Electronic"
    METAL = "Metal"
    HIP_HOP = "Hip-Hop"


class URLType(Enum):
    ROLE = "Role"
    ROLEHUB = "RoleHub"


## THESe should all move to the inits of each model
class LLM(Enum):
    GPT3 = "gpt-3.5-turbo-0125"
    GPT4 = "gpt-4-turbo-2024-04-09"
    CLAUD3_OPUS = "claude-3-opus-20240229"


class AIEventType(Enum):
    CREATE = "Create"
    CHAT = "chat"
    FUNCTION = "function"
    KILL = "kill"
    CONTEXT = "context"


class AIEventStatus(Enum):
    STARTED = "started"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


class AIEvent(Enum):
    CREATE_AI = "createAI"
    PARSE_ROLE_HTML = "parseRoleHTML"
    LOAD_CONTEXT = "load_context"
    GENERATE_PROMPT = "generate_prompt"


class SourceType(Enum):
    FILE = "file"
    OBJECT = "object"
