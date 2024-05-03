# # https://python.langchain.com/docs/modules/model_io/chat/structured_output/


from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI


from langchain_google_vertexai import ChatVertexAI

import vertexai
from vertexai.preview import reasoning_engines

from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-3-opus-20240229")

# vertexai.init(
#     project="portfolio-383615",
#     location="us-central1",
#     staging_bucket="gs://jobbr",
# )
# model = "gemini-1.0-pro"


class Joke(BaseModel):
    setup: str = Field(description="The setup of the joke")
    punchline: str = Field(description="The punchline to the joke")


model = ChatAnthropic(model="claude-3-opus-20240229", temperature=0)
structured_llm = model.with_structured_output(Joke)
x = structured_llm.invoke(
    "Tell me a joke about cats. Make sure to call the Joke function."
)
print(x)
print(x.setup)
