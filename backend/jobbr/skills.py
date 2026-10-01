"""Skill taxonomy + normalisation. Canonical names with aliases; used for resumes and postings."""

import re

# canonical -> aliases (all matched case-insensitively on word boundaries)
TAXONOMY: dict[str, list[str]] = {
    "python": [], "typescript": ["ts"], "javascript": ["js", "ecmascript"], "go": ["golang"],
    "rust": [], "java": [], "kotlin": [], "swift": [], "c++": ["cpp"], "c#": ["csharp"],
    "ruby": [], "scala": [], "sql": [], "r": [], "bash": ["shell scripting"],
    "react": ["react.js", "reactjs"], "next.js": ["nextjs"], "vue": ["vue.js"], "angular": [],
    "node.js": ["nodejs", "node"], "fastapi": [], "django": [], "flask": [], "spring": ["spring boot"],
    "rails": ["ruby on rails"], "graphql": [], "rest": ["rest api", "restful"], "grpc": [],
    "postgres": ["postgresql"], "mysql": [], "mongodb": [], "redis": [], "kafka": [],
    "elasticsearch": ["opensearch"], "snowflake": [], "bigquery": [], "dbt": [], "airflow": [],
    "spark": ["pyspark", "apache spark"], "flink": [], "hadoop": [], "databricks": [],
    "aws": ["amazon web services"], "gcp": ["google cloud"], "azure": [],
    "kubernetes": ["k8s"], "docker": [], "terraform": [], "helm": [], "ci/cd": ["cicd", "continuous integration"],
    "linux": [], "git": [], "prometheus": [], "grafana": [], "datadog": [],
    "machine learning": ["ml"], "deep learning": [], "nlp": ["natural language processing"],
    "llm": ["llms", "large language models"], "rag": ["retrieval augmented generation"],
    "pytorch": [], "tensorflow": [], "scikit-learn": ["sklearn"], "pandas": [], "numpy": [],
    "langchain": [], "mlops": [], "data engineering": [], "data modeling": ["data modelling"],
    "system design": ["distributed systems"], "microservices": [], "observability": [],
    "tableau": [], "looker": [], "excel": [], "figma": [], "product management": [],
    "agile": ["scrum"], "security": ["appsec"], "testing": ["unit testing", "tdd"],
}

_ALIAS: dict[str, str] = {}
for canon, aliases in TAXONOMY.items():
    _ALIAS[canon] = canon
    for a in aliases:
        _ALIAS[a] = canon

AMBIGUOUS = {"go", "r"}  # only count as skills inside a comma/slash list, case-sensitively
_PATTERNS: list[tuple[str, re.Pattern]] = []
for alias, canon in sorted(_ALIAS.items(), key=lambda kv: -len(kv[0])):
    if alias in AMBIGUOUS:
        continue
    esc = re.escape(alias)
    _PATTERNS.append((canon, re.compile(rf"(?<![\w+#.]){esc}(?![\w+#]|\.\w)", re.I)))
_LIST_CTX = {c: re.compile(rf"(?:[,/]\s*{c.capitalize() if c == 'go' else 'R'}\b|\b{c.capitalize() if c == 'go' else 'R'}\b\s*[,/])") for c in AMBIGUOUS}


def normalize_skill(s: str) -> str:
    t = re.sub(r"\s+", " ", s.strip().lower())
    return _ALIAS.get(t, t)


def normalize_skills(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for s in items:
        n = normalize_skill(s)
        if n and len(n) <= 40:
            seen[n] = None
    return list(seen)


def find_skills(text: str) -> list[str]:
    """Scan free text for taxonomy skills (word-boundary, case-insensitive)."""
    found: dict[str, None] = {}
    for canon, pat in _PATTERNS:
        if pat.search(text):
            found[canon] = None
    for canon, pat in _LIST_CTX.items():
        if pat.search(text):
            found[canon] = None
    return list(found)
