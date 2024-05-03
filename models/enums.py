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
    CREATE = "create"
    CHAT = "chat"
    FUNCTION = "function"
    KILL = "kill"


class AIEventStatus(Enum):
    STARTED = "started"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"


class AIFunction(Enum):
    CREATEAI = "createAI"
    PARSEROLEHTML = "parseRoleHTML"
