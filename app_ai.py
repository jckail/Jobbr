from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from datetime import datetime
from uuid import UUID, uuid4

from models import (
    LLM,
    AIEventType,
    AIEventStatus,
    AIEvent,
    App_AI,
    App_AI_Event,
    Stg_Role,
    Stg_RoleBase,
)


from typing import Optional, List, Any
from pydantic import BaseModel
from helpers import load_file
from enum import Enum
from langchain.prompts import ChatPromptTemplate


class SourceType(Enum):
    FILE = "file"
    OBJECT = "object"


## will create a context ownership model


### context items are not bound to a particualr ai
class AI_CONTEXT_ITEM:
    def __init__(
        self,
        source_name: str,
        type: SourceType,
        alias: str = None,
        data: Any = None,
        estimated_tokens: int = None,
        context_owner_id: UUID = None,  # owner of the context
        authorized_users: List[
            UUID
        ] = None,  # a list of users allowed to access the context
    ):
        self.context_owner_id = context_owner_id
        self.authorized_users = authorized_users
        self.id = uuid4()
        self.source_name = (
            source_name  # can be the name of an object alias OR name of a file
        )
        if alias:
            self.alias = alias
        else:
            self.alias = self.source_name
        self.type = type
        if data:
            self.data = data
        else:
            if self.type == SourceType.FILE:
                self.data = load_file(
                    source_name
                )  # modify in helpersfor other file types

        if estimated_tokens:
            self.estimated_tokens = estimated_tokens
        else:
            self.estimated_tokens = len(self.data)  # this might break outside of HTML

        #### EVENTUALLY MAP THIS TO A VECTOR QUERY //UUID
        #### EVENTUALLY MAP THIS TO A SQL UUID


### AI contains context items context items are not bound to a particualr ai
class AI_CONTEXT:
    def __init__(
        self,
        app_ai_id: UUID,
        specified_context: Optional[List] = [],
        context_items: Optional[List[AI_CONTEXT_ITEM]] = None,
    ):

        self.specified_context = specified_context
        self.app_ai_id = app_ai_id
        self.id = uuid4()
        self.context_items = {}
        if context_items:
            for ci in context_items:
                self.context_items[ci.id] = ci

    def addExistingAI_CONTEXT_ITEM(self, ci: AI_CONTEXT_ITEM):
        self.context_items[ci.id] = ci

    def addAI_CONTEXT_ITEM(
        self,
        source_name: str,
        type: SourceType,
        alias: str = None,
        data: Any = None,
        estimated_tokens: int = None,
    ):
        ci = AI_CONTEXT_ITEM(source_name, type, alias, data, estimated_tokens)
        self.context_items[ci.id] = ci
        return ci


class JobbrAI:
    def __init__(self, llm: LLM = LLM.GPT3, temperature=0, max_tokens=None):

        self.id = uuid4()
        self.model_creation_utc = int(datetime.now().timestamp())
        if llm in [LLM.GPT3, LLM.GPT4]:
            self.model_engine = ChatOpenAI(model=llm.value, temperature=temperature)

        elif llm in [LLM.CLAUD3_OPUS]:
            self.model_engine = ChatAnthropic(model=llm.value, temperature=temperature)
            ## don't forget custom names loading outputs to this vs open ai
        else:
            raise ValueError("Model not supported")

        if max_tokens:
            self.max_tokens = max_tokens
        else:
            if llm == LLM.GPT3:
                self.max_tokens = 16000
            elif llm == LLM.GPT4:
                self.max_tokens = 100000
            elif llm == LLM.CLAUD3_OPUS:
                self.max_tokens = 65000
            else:
                self.max_tokens = 16000

        self.model = llm
        self.temperature = temperature
        self.lastEvent = None
        self.context = AI_CONTEXT(self.id)
        self.save_app_ai()

        self.parseDataPromptTemplate = """

            -----------------
            -----------------

            question: 
            "{question}" 


            Answer the qustion provided only the documents and context I give you:

            Contexts:
            {context} 



            """
        self.currentPrompt = ""

    def tokenEstimator(data):
        return len(data) // 4

    ### add in prompt functionality

    def save_app_ai_events(
        self,
        event_type: AIEventType,
        event: AIEvent,
        event_status: AIEventStatus,
        estimated_tokens: int = None,
        messages: List[str] = None,
    ):
        if self.lastEvent:
            le = self.lastEvent.event_utc
        else:
            le = None
        ae = App_AI_Event(
            app_ai_id=self.id,
            model=self.model,
            temperature=self.temperature,
            event_type=event_type,
            event=event,
            event_status=event_status,
            function_start_utc=le,
            estimated_tokens=estimated_tokens,
            messages=messages,
        )
        self.lastEvent = ae
        ae.saveModel()

        return ae

    def save_app_ai(self):

        aa = App_AI(
            id=self.id,
            model=self.model,
            temperature=self.temperature,
            ai_context_id=self.context.id,
        )
        aa.saveModel()

        ae = self.save_app_ai_events(
            event_type=AIEventType.CREATE,
            event=AIEvent.CREATE_AI,
            event_status=AIEventStatus.COMPLETED,
        )
        ae.saveModel()

    def loadContextFile(self, file, alias: str = None):
        try:
            self.save_app_ai_events(
                event_type=AIEventType.CONTEXT,
                event=AIEvent.LOAD_CONTEXT,
                event_status=AIEventStatus.STARTED,
                messages=[file, alias],
            )
            ci = self.context.addAI_CONTEXT_ITEM(
                source_name=file, type=SourceType.FILE, alias=alias
            )
            self.save_app_ai_events(
                event_type=AIEventType.CONTEXT,
                event=AIEvent.LOAD_CONTEXT,
                event_status=AIEventStatus.COMPLETED,
                messages=[file, alias, str(ci.id)],
            )
            return ci

        except Exception as e:
            print(f"Failed to intially load file {file}: {str(e)}")
            self.save_app_ai_events(
                event_type=AIEventType.CONTEXT,
                event=AIEvent.LOAD_CONTEXT,
                event_status=AIEventStatus.FAILED,
                messages=[file, alias],
            )

    def generatePrompt(self, query, prompt_template: str):

        contextList = []
        for id in self.context.context_items:
            if id in self.context.specified_context:
                contextList.append(
                    f"{self.context.context_items[id]} generated from {self.context.context_items[id].source_name}: {self.context.context_items[id].data}"
                )

        context = "\n---\n ".join(contextList)

        prompt_template = ChatPromptTemplate.from_template(prompt_template)
        return prompt_template.format(context=context, question=query)

    def parseRoleHTML(self, roleHTMLFile, alias: str = None):
        f = Stg_RoleBase.__doc__

        userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting"

        if not alias:
            alias = roleHTMLFile

        ci = self.loadContextFile(roleHTMLFile, alias=alias)
        self.context.specified_context = [ci.id]
        self.parseToDataModel(
            Stg_Role,
            AIEvent.PARSE_ROLE_HTML,
            userMessage,
            extra_data={"url": alias},
        )

    def parseToDataModel(
        self,
        targetBaseModel: BaseModel,
        aiEvent: AIEvent,
        userMessage: str = None,
        extra_data: dict = None,
    ):

        if not userMessage:
            userMessage = " Convert the following text to exactly the desired json format provided. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None."

        prompt = self.generatePrompt(
            userMessage,
            self.parseDataPromptTemplate,
            specified_context=self.context.specified_context,
        )

        estimatedTokens = len(prompt) // 4

        self.save_app_ai_events(
            event_type=AIEventType.FUNCTION,
            event=aiEvent,
            event_status=AIEventStatus.STARTED,
            estimated_tokens=estimatedTokens,
            messages=[userMessage],
        )

        try:
            if estimatedTokens > self.max_tokens:
                # throw exception
                raise ValueError(
                    f"Too many tokens in one query, max set to {self.max_tokens}"
                )
            structured_llm = self.model_engine.with_structured_output(
                targetBaseModel, include_raw=True, method="json_mode"
            )

            x = structured_llm.invoke(input=prompt)
            z = x["raw"]
            payload = x["parsed"]
            parsing_error = str(x["parsing_error"])
            print(x)
            if not z:
                raise ValueError("No metadata response from model")
            if not payload:
                raise ValueError("No parsed response from model")

            ##TODO remove all custom fields on a parseModel -- maybe create these as a base class as needed or append payload with values
            baseModel = targetBaseModel(
                **payload,  # this should fill whatever base
                ai_app_event_id=self.lastEvent.id,  # this should
                specified_context=specified_context,  ##TODO Replace this with contextIDs
                context_id=self.context.id,
                extra_data=extra_data,
                ## add contexts
            ).saveModel()

            if self.model in [LLM.GPT3, LLM.GPT4]:
                airR = App_AI_Event(
                    app_ai_id=self.id,
                    model=self.model,
                    temperature=self.temperature,
                    event_type=self.lastEvent.event_type,
                    event=self.lastEvent.event,
                    event_status=AIEventStatus.COMPLETED,
                    function_start_utc=self.lastEvent.event_utc,
                    response_id=z.response_metadata["system_fingerprint"],
                    stop_reason=z.response_metadata["finish_reason"],
                    stop_sequence=None,
                    input_tokens=z.response_metadata["token_usage"]["prompt_tokens"],
                    output_tokens=z.response_metadata["token_usage"][
                        "completion_tokens"
                    ],
                    parsing_error=parsing_error,
                )
                airR.saveModel()

            elif self.model in [LLM.CLAUD3_OPUS]:
                airR = App_AI_Event(
                    app_ai_id=self.id,
                    model=self.model,
                    temperature=self.temperature,
                    event_type=self.lastEvent.event_type,
                    event=self.lastEvent.event,
                    event_status=AIEventStatus.COMPLETED,
                    function_start_utc=self.lastEvent.event_utc,
                    response_id=z.response_metadata["id"],
                    stop_reason=z.response_metadata["stop_reason"],
                    stop_sequence=z.response_metadata["stop_sequence"],
                    input_tokens=z.response_metadata["usage"]["input_tokens"],
                    output_tokens=z.response_metadata["usage"][
                        "output_tokens"
                    ],  # openai  completion_tokens #claude output_tokens
                    parsing_error=parsing_error,
                )
                airR.saveModel()
            return baseModel

        except Exception as e:

            print(f"\n Failed parseToDataModel. Error: {e}")
            self.save_app_ai_events(
                event_type=AIEventType.FUNCTION,
                event=AIEvent.PARSE_ROLE_HTML,
                event_status=AIEventStatus.FAILED,
                messages=[str(e)],
            )


if __name__ == "__main__":
    html_file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
    ai = JobbrAI()
    ai.parseRoleHTML(html_file)
