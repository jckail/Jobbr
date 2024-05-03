# use with structuredoutput

# https://python.langchain.com/docs/modules/model_io/chat/structured_output/
import glob
from datetime import datetime
import random
import os
import time
from magentic import (
    chatprompt,
    AssistantMessage,
    SystemMessage,
    UserMessage,
    OpenaiChatModel,
)
from sqlmodel import SQLModel, Field
from uuid import UUID, uuid4
from pydantic import BaseModel, HttpUrl
from typing import Optional, List

from models.mixins import BaseMixin
from sqlalchemy.dialects import postgresql
from sqlmodel import (
    Field,
    Session,
    SQLModel,
    create_engine,
    JSON,
    Column,
    String,
    Integer,
)
from db import init_db, engine
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think
class StageRoleBase(BaseMixin, SQLModel):
    """
    Pydantic Basemodel

    company_name (str): The name of the company associated with the role.
    title (str): The title of the role.
    description (str)): A short under 75 word description and responsibilities and expectations of the role and not of the company.
    location (str): A list of locations avalible for the role IE: city,state San Francisco, California or Atlanta, Georgia.
    remote (str)): If the role allows remote work in any capacity.
    in_person (str)): If the role requires the person to go into the office or be in person.
    travel (str): The travel frequency requirements of the role.
    soft_skills (List[str]): The soft skills required for the role.
    technical_skills (List[str]): The technical skills required for the role.
    certifications (List[str]): Ideal certifications for the role.
    years_of_experience (int): The estimated years of experience for the role.
    prior_experience_description (str): Description of any desired previous experience.
    estimated_career_level (str): An estimation of what level at the company this is IE is a junior, midlevel, senior, manager, director or leadership role could be another value.
    estimated_min_compensation (int): The estimated minimum compensation for the role.
    estimated_max_compensation (int): The estimated maximum compensation for the role.
    compensation_description (str): Details around the compensation for the role including a range.
    pto_and_benefits (str): The benefits and PTO information for the role.
    role_quirks (str): Anything that stands out about the role being unique or bizzare.
    ai_analysis (str): This field should be blank.
    estimated_status (str): This is a best guess if the role is still avalible based on there being a job description on the page.


    """

    company_name: str
    title: Optional[str]
    description: Optional[str]
    location: Optional[str]
    remote: Optional[str]
    in_person: Optional[str]
    travel: Optional[str]
    soft_skills: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    technical_skills: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    certifications: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    years_of_experience: Optional[int]
    prior_experience_description: Optional[str]
    estimated_career_level: Optional[str]
    education_requirement: Optional[str]
    estimated_min_compensation: Optional[int]
    estimated_max_compensation: Optional[int]
    compensation_description: Optional[str]
    pto_and_benefits: Optional[str]
    role_quirks: Optional[str]
    ai_analysis: Optional[str] = None
    estimated_status: Optional[str]

    class Config:
        """
        Pydantic model configuration.

        Configures the model settings, such as enabling ORM mode.
        """

        from_attributes = True  # if using Pydantic v2


class StageRole(StageRoleBase, table=True):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # backpopulates u
    AIFunctionRun_id: UUID
    file_source: Optional[str]
    url: Optional[str]
    status: Optional[str]


class AIFunctionRunBase(BaseMixin, SQLModel):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    ## ADD IN PROMPT for user and system
    ## add in contexts and sources
    ## follow langchain terms
    input_model: str
    tokenCount: int
    function: str
    tries: int
    file_source: Optional[str]
    url: Optional[str]
    run_start_utc: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()), nullable=False
    )
    # add in query


class AIFunctionRun(AIFunctionRunBase, table=True):
    """
    id the uuid of the record
    file_source the source file of the role
    url : the orignal URL from the previous call
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True)  # backpopulates u
    # add in query


class AIFunctionResult(AIFunctionRunBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)  # backpopulates u
    AIFunctionRun_id: UUID
    success: bool
    message: str
    # Adding new fields to store additional metadata
    model: Optional[str] = Field(default=None, description="The model used for the run")
    response_id: Optional[str] = Field(
        default=None, description="Response ID of the model"
    )
    stop_reason: Optional[str] = Field(
        default=None, description="Reason why the model stopped"
    )
    stop_sequence: Optional[str] = Field(
        default=None, description="Sequence at which the model stopped"
    )
    input_tokens: Optional[int] = Field(
        default=0, description="Number of input tokens used"
    )
    output_tokens: Optional[int] = Field(
        default=0, description="Number of output tokens generated"
    )
    parsing_error: Optional[str] = Field(
        default=0, description="Parsing Errors Encountered"
    )
    run_completion_utc: int = Field(
        default_factory=lambda: int(datetime.now().timestamp()), nullable=False
    )


systemMessage = "Parse the information on a job posting to the exact json format I am requesting to the best of your ability for fields that are."
userMessage = "Parse this data {html} to the exact format I am requesting."


# @chatprompt(
#     SystemMessage(systemMessage),
#     UserMessage(userMessage),
#     model=OpenaiChatModel("gpt-3.5-turbo"),
# )
# def parseHTML35(html: str) -> StageRoleBase: ...


# @chatprompt(
#     SystemMessage(systemMessage),
#     UserMessage(userMessage),
# )
# def parseHTML4(html: str) -> StageRoleBase: ...


f = """
    Pydantic Basemodel

    company_name (str): The name of the company associated with the role.
    title (str): The title of the role.
    description (str)): A short under 75 word description and responsibilities and expectations of the role and not of the company.
    location (str): A list of locations avalible for the role IE: city,state San Francisco, California or Atlanta, Georgia.
    remote (str)): If the role allows remote work in any capacity.
    in_person (str)): If the role requires the person to go into the office or be in person.
    travel (str): The travel frequency requirements of the role.
    soft_skills (List[str]): The soft skills required for the role.
    technical_skills (List[str]): The technical skills required for the role.
    certifications (List[str]): Ideal certifications for the role.
    years_of_experience (int): The estimated years of experience for the role.
    prior_experience_description (str): Description of any desired previous experience.
    estimated_career_level (str): An estimation of what level at the company this is IE is a junior, midlevel, senior, manager, director or leadership role could be another value.
    estimated_min_compensation (int): The estimated minimum compensation for the role.
    estimated_max_compensation (int): The estimated maximum compensation for the role.
    compensation_description (str): Details around the compensation for the role including a range.
    pto_and_benefits (str): The benefits and PTO information for the role.
    role_quirks (str): Anything that stands out about the role being unique or bizzare.
    ai_analysis (str): This field should be blank.
    estimated_status (str): This is a best guess if the role is still avalible based on there being a job description on the page.


    """


def parseHTMLClaud3(html):
    userMessage = f"Parse the following job posting text into JSON format {f} according to the specified structure. Ensure that all requested fields are included in the output. If any data is missing or unavailable, populate them as None (use null values). Some details may not be explicitly mentioned, do your best to infer them. Here is the text: {html}"
    model = ChatAnthropic(
        model="claude-3-opus-20240229", temperature=0
    )  # claude-3-haiku-20240307 # claude-3-sonnet-20240229 #claude-3-opus-20240229
    structured_llm = model.with_structured_output(StageRoleBase, include_raw=True)
    # print(structured_llm)
    # print(userMessage)
    return structured_llm.invoke(input=userMessage)


def parseHTMLgpt3(html):
    userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting: {html}"
    model = ChatOpenAI(
        model="gpt-3.5-turbo-0125", temperature=0
    )  # claude-3-haiku-20240307 # claude-3-sonnet-20240229 #claude-3-opus-20240229
    structured_llm = model.with_structured_output(
        StageRoleBase, include_raw=True, method="json_mode"
    )
    # print(structured_llm)
    # print(userMessage)
    return structured_llm.invoke(input=userMessage)


def parseHTMLgpt4(html):
    userMessage = f" Convert the following job posting text to exactly the desired json format {f}. Do not add in any new field names use only the ones I have previously provided. If there are any values that cannot be calculated return those as None. If there is a mention of 'not found' assume the role has been filled and the status is closed. Here is the job posting: {html}"
    model = ChatOpenAI(
        model="gpt-4-turbo-2024-04-09", temperature=0
    )  # claude-3-haiku-20240307 # claude-3-sonnet-20240229 #claude-3-opus-20240229
    structured_llm = model.with_structured_output(
        StageRoleBase, include_raw=True, method="json_mode"
    )
    # print(structured_llm)
    # print(userMessage)
    return structured_llm.invoke(input=userMessage)


def filter_files(file_list):
    suffixes = ["_visible_text.txt", "_script_texts.txt", "_meta_contents.txt"]
    # Filter the list to exclude files that end with the specified suffixes
    filtered_list = [
        file
        for file in file_list
        if not any(file.endswith(suffix) for suffix in suffixes)
    ]
    return filtered_list


def get_all_html_files(directory, file_type):
    html_files = []
    for subdir in os.scandir(directory):
        if subdir.is_dir():
            html_files.extend(
                glob.glob(f"{subdir.path}/**/*.{file_type}", recursive=True)
            )
    return filter_files(html_files)


def load_html(file_path):
    with open(file_path, "r") as file:
        data = file.read()
    return data


def get_number_of_characters(file_path):
    with open(file_path, "r") as file:
        contents = file.read().replace("\n", "")
    return len(contents)


def random_sleep():
    # Generate a random number between 5 and 15
    sleep_time = random.randint(10, 15)
    # Sleep for the generated number of seconds
    time.sleep(sleep_time)
    print(f"Slept for {sleep_time} seconds")


def loadLoopFile(file):
    try:
        html = load_html(file)
        tokenCount = len(html) // 4
        return html, tokenCount
    except Exception as e:
        print(f"Failed to load file {file}: {str(e)}")


def process_file(file):

    max_tries = 3
    tries = 0
    dump = None
    model = "3.5"

    while tries < max_tries:
        tries += 1
        html, tokenCount = loadLoopFile(file)
        if tokenCount >= 16000 and tries == 1:
            try:
                file = file.replace(".txt", "_visible_text.txt")
                html, tokenCount = loadLoopFile(file)
            except Exception as e:
                print(f"Failed to load file {file}: {str(e)}")

        if tries == 2 or tokenCount >= 16000:
            model = "claude"

        if tries == 3:
            model = "4"
            file = file.replace(".txt", ".html")
            html, tokenCount = loadLoopFile(file)
        tokenMax = 75000
        if tokenCount > tokenMax:
            # raise exception too many tokens in one query
            raise Exception(f"Too many tokens in one query, max set to {tokenMax}")

        print(
            f"\n\n-----\n\nModel:{model}\nParsing: {file} \n Tokens: {tokenCount} \n Try:{tries}\n\n-----\n"
        )
        try:

            # this should be populated within the call to AIFunctionRun
            a = {
                "input_model": model,
                "tokenCount": tokenCount,
                "function": "parseStageRoleHtml",
                "tries": tries,
                "file_source": file,
                "url": None,
            }
            aib = AIFunctionRunBase(**a)
            air = AIFunctionRun(**aib.model_dump())

            dump = air.model_dump()
            with Session(engine) as session:
                session.add(air)
                session.commit()

            fkid = dump.pop("id", None)
            if model == "4":
                x = parseHTMLgpt4(html)
            elif model == "3.5":
                x = parseHTMLgpt3(html)
            elif model == "claude":
                x = parseHTMLClaud3(html)
            else:
                raise ValueError("Model not supported")

            #
            # print("\n----\n\n----\n")
            # print("\n--x[raw]--\n", x, "\n----")
            # z = x["raw"]
            # # print("\n----\n", z.response_metadata, "\n----")
            # # print("\n----\n", z, "\n----")
            # print(f"\n--Parsed--\n {z.content[0]} \n----\n")
            # print(f"\n--Parsed--\n {x["parsed"]} \n----\n")

            if not x["parsed"]:
                raise ValueError("No parsed response from model")

            payload = x["parsed"]
            role = StageRole(
                **payload,
                AIFunctionRun_id=fkid,
                file_source=file,
                status="active",
            )
            z = x["raw"]
            # print(f"n\n\ncontent {z.content}\n\n\n")
            if model in ["3.5", "4"]:

                airR = AIFunctionResult(
                    **a,
                    AIFunctionRun_id=fkid,
                    success=True,
                    message="success",
                    model=z.response_metadata["model_name"],
                    response_id=z.response_metadata["system_fingerprint"],
                    stop_reason=z.response_metadata["finish_reason"],
                    stop_sequence=None,
                    input_tokens=z.response_metadata["token_usage"]["prompt_tokens"],
                    output_tokens=z.response_metadata["token_usage"][
                        "completion_tokens"
                    ],  # openai  completion_tokens #claude output_tokens
                    parsing_error=str(x["parsing_error"]),
                )
            elif model == "claude":
                airR = AIFunctionResult(
                    **a,
                    AIFunctionRun_id=fkid,
                    success=True,
                    message="success",
                    model=z.response_metadata["model"],
                    response_id=z.response_metadata["id"],
                    stop_reason=z.response_metadata["stop_reason"],
                    stop_sequence=z.response_metadata["stop_sequence"],
                    input_tokens=z.response_metadata["usage"]["input_tokens"],
                    output_tokens=z.response_metadata["usage"][
                        "output_tokens"
                    ],  # openai  completion_tokens #claude output_tokens
                    parsing_error=str(x["parsing_error"]),
                )
            with Session(engine) as session:
                session.add(role)
                session.add(airR)
                session.commit()
            print(
                f"\n\n---Completed---\n\nModel:{model}\nParsing: {file} \n Tokens: {tokenCount} \n Try:{tries}\n\n-----\n"
            )
            return True
        except Exception as e:

            print(f"\n Failed to process file {file}. Error: {e}")
            traceback.print_exc()  # This will print the stack trace
            if tries < max_tries:
                print(f"Retrying in 5 seconds... (Attempt {tries+1} of {max_tries})")
                random_sleep()
            else:
                print(f"Failed to process file {file} after {max_tries} attempts.")
            try:
                airR = AIFunctionResult(
                    **a, AIFunctionRun_id=fkid, success=False, message=str(e)
                )
                with Session(engine) as session:
                    session.add(airR)
                    session.commit()
            except Exception as e:
                print(f"Failed to log error for file {file}. Error: {e}")

    print(
        f"\n\n---Failed---\n\nModel:{model}\nParsing: {file} \n Tokens: {tokenCount} \n Try:{tries}\n\n-----\n"
    )

    return False


if __name__ == "__main__":
    file = "/Users/jordankail/Jobbr/scraped_data/openai/careers_analytics_data_engineer_applied_engineering.txt"
    file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
    file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
    directory = "scraped_data/"

    import concurrent.futures

    import traceback

    import time

    init_db()
    ##process_file(file)

    # with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    #     executor.map(process_file, get_all_html_files(directory, "txt"))
    # Define a function to process a file and return the result if any

    def process_and_yield(file):
        result = process_file(file)
        if result:
            return result
        print("thread_sleeping")
        random_sleep()

    # Get all HTML files in the directory
    files = get_all_html_files(directory, "txt")

    # Submit tasks to the executor and process the results as they complete
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_and_yield, file) for file in files]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                print(result)
                # Do something with the result
