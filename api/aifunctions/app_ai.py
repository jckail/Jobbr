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
    Stg_RoleBase,
    SourceType,
)
from dotenv import load_dotenv
import os


from typing import Optional, List, Tuple
from pydantic import BaseModel
from langchain.prompts import ChatPromptTemplate
from .ai_context import AI_CONTEXT
load_dotenv()

## will create a context ownership model


class JobbrAI:
    def __init__(self, llm: LLM = LLM.GPT3, temperature=0, max_tokens=None):
        self.estimated_tokens = None
        self.id = uuid4()
        self.model_creation_utc = int(datetime.now().timestamp())
        if llm in [LLM.GPT3, LLM.GPT4]:
            self.model_engine = ChatOpenAI(model=llm.value, temperature=temperature)

        elif llm in [LLM.CLAUD3_OPUS]:
            self.model_engine = ChatAnthropic(model=llm.value, temperature=temperature,api_key=str(os.getenv('ANTHROPIC_API_KEY')),)
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
        


        self.currentPrompt = ""

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

    def loadContextFile(
        self,
        source_name: str,
        source_id: Optional[UUID] = None,
        description: str = None,
        alias: str = None,
        extra_data: dict = None,
    ):
        try:
            self.save_app_ai_events(
                event_type=AIEventType.CONTEXT,
                event=AIEvent.LOAD_CONTEXT,
                event_status=AIEventStatus.STARTED,
                messages=[source_name, alias],
            )

            ci = self.context.add_ai_context_item(
                source_name=source_name,
                source_id=source_id,
                source_type=SourceType.FILE,
                description=description,
                alias=alias,
                extra_data=extra_data,
            )
            self.save_app_ai_events(
                event_type=AIEventType.CONTEXT,
                event=AIEvent.LOAD_CONTEXT,
                event_status=AIEventStatus.COMPLETED,
                estimated_tokens = ci.estimated_tokens,
                messages=[source_name, alias, str(ci.id)],
            )
            return ci

        except Exception as e:
            print(f"Failed to intially load file {source_name}: {str(e)}")
            self.save_app_ai_events(
                event_type=AIEventType.CONTEXT,
                event=AIEvent.LOAD_CONTEXT,
                event_status=AIEventStatus.FAILED,
                messages=[source_name, alias, ],
            )
            raise

    def generateContext(self):
        """
        TODO:  THis should become a method to turn specific context to one context
        """
        try:
            contextList = []
            for id in self.context.context_items:
                if id in self.context.specified_context_ids:
                    contextItem = self.context.context_items[id]
                    contextList.append(
                        f"{contextItem.alias} generated from {contextItem.source_name}: {contextItem.data}"
                    )

            return "\n----\n".join(contextList)


        except Exception as e:
            print(f"Aggregating context lists: {e}")
            raise


    def setEstimatedTokens(self, characterCount):
        self.estimated_tokens = len(characterCount) // 4

        if self.estimated_tokens > self.max_tokens:
            # throw exception
            raise ValueError(
                f"Too many tokens in one query, max set to {self.max_tokens}"
            )
        return self.estimated_tokens

    def generateParseDataPrompt(self, userMessage, modelDocString):
        try:
            parseDataPromptTemplate = """

Data to Parse to JSON: You will receive the specific data that needs to be converted to a specified JSON format. Use this data in accordance with the above instructions to generate the output.

Data Schema: Refer to the provided schema which includes data types and descriptions for each field. Ensure that the JSON output matches the schema exactly in terms of field names and data types.
Handling Missing Data: If any data required by the schema is missing, assign the value null to the corresponding field in the JSON output.
Handling Uncertainties: If you are unsure about what data corresponds to a field, use your best judgement to make an educated guess. If completely unsure, you may also use null as a placeholder.
Field Completeness: Aim to populate as many fields as possible in the JSON output. The priority is to ensure that field names and data types are correct. Maximizing the number of populated fields is secondary but also important.
Example Output: An example of the desired JSON format will be provided. Use this as a guide to understand how the final output should look.
Final Output: Ensure the JSON output is well-formed, with correct syntax and structure. Use standard JSON formatting practices.

                {userMessage} 

                Data Schema:
                {modelDocString} 

                Data to Parse to JSON:
                {context}

                """
            
            prompt_template = ChatPromptTemplate.from_template(parseDataPromptTemplate)
            prompt = prompt_template.format(context=self.generateContext(), userMessage=userMessage, modelDocString=modelDocString)

            self.setEstimatedTokens(prompt)
            return prompt
        except Exception as e:
            # Handle general errors
            print(f"An error occurred: {str(e)}")



    def parseToDataModel(
        self,
        targetBaseModel: BaseModel,
        aiEvent: AIEvent,
        userMessage: str = None,
        extra_data: dict = None,
    ) -> Tuple[BaseModel, dict]:
        

        prompt = self.generateParseDataPrompt(userMessage,targetBaseModel.__doc__ )

        self.save_app_ai_events(
            event_type=AIEventType.FUNCTION,
            event=aiEvent,
            event_status=AIEventStatus.STARTED,
            estimated_tokens=self.estimated_tokens,
            messages=[userMessage],
        )
        
        try:
            x = None
            if self.model in [LLM.GPT3, LLM.GPT4]:
                structured_llm = self.model_engine.with_structured_output(
                targetBaseModel, include_raw=True, method="json_mode"
            )
            elif self.model in [LLM.CLAUD3_OPUS]:
                structured_llm = self.model_engine.with_structured_output(targetBaseModel, include_raw=True)

            else:
                # raise an error indicating the llm has not been configured
                raise ValueError(f"Model:{self.model.value} not supported")

            x = structured_llm.invoke(input=prompt)
            z = x["raw"]
            payload = x["parsed"]
            parsing_error = str(x["parsing_error"])

            if not z:
                raise ValueError("No metadata response from model")
            if not payload:
                raise ValueError("No parsed response from model")

            ##TODO remove all custom fields on a parseModel -- maybe create these as a base class as needed or append payload with values
            baseModel = targetBaseModel(**payload)

            if self.model in [LLM.GPT3, LLM.GPT4]:
                print(f"\n---\nInput Tokens: {z.response_metadata["token_usage"]["prompt_tokens"]} \n---\n")
                airR = App_AI_Event(
                    app_ai_id=self.id,
                    model=self.model,
                    temperature=self.temperature,
                    estimated_tokens = self.estimated_tokens, 
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
                    messages=[str(payload)],
                )
                airR.saveModel()

            elif self.model in [LLM.CLAUD3_OPUS]:
                #print(f"\n---\nInput Tokens: {z.response_metadata["token_usage"]["prompt_tokens"]} \n---\n")
                airR = App_AI_Event(
                    app_ai_id=self.id,
                    model=self.model,
                    temperature=self.temperature,
                    estimated_tokens = self.estimated_tokens, 
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
                    messages=[str(payload)],
                )
                airR.saveModel()

            self.lastEvent = airR
            return baseModel, {
                "app_ai_id" :self.lastEvent.app_ai_id,
                "app_ai_event_id": self.lastEvent.id,
                "specified_context_ids": [
                    str(x) for x in self.context.specified_context_ids
                ],
                "context_id": self.context.id,
                "extra_data": extra_data,
            }

        except Exception as e:

            print(f"\n Failed parseToDataModel. Error: {e}")
            self.save_app_ai_events(
                event_type=AIEventType.FUNCTION,
                event=AIEvent.PARSE_ROLE_HTML,
                event_status=AIEventStatus.FAILED,
                estimated_tokens = self.estimated_tokens, 
                messages=[str(e),str(x),prompt],
            )
            raise


if __name__ == "__main__":
    html_file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
    ai = JobbrAI()
    ai.parseRoleHTML(html_file)
