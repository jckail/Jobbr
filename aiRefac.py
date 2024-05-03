# ok you don't need to load more data
# you need to refactor this code so that an api call can run this
# fix URL and user add information?
# scale this to load into vectorDB too
# then create chat interface APIs on each?
# also chain in fit scores from role to candidate
# add in normalization step from many roles records to one roles record

import glob
import random
import os
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
from sqlmodel import Field, Session, SQLModel, create_engine, JSON, Column, String
from db import init_db, engine
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


import instructor
from pydantic import BaseModel
from openai import OpenAI


##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think
class RoleBase(BaseMixin, SQLModel):
    """
    Pydantic Basemodel

    company_name (str): The name of the company associated with the role.
    title (str): The title of the role.
    description (str)): A short under 100 word description and responsibilities and expectations of the role of the role not the company.
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


    """

    company_name: str
    title: str
    description: str
    location: str
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

    class Config:
        """
        Pydantic model configuration.

        Configures the model settings, such as enabling ORM mode.
        """

        from_attributes = True  # if using Pydantic v2


class Role(RoleBase, table=True):
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


def load_html(file_path):
    with open(file_path, "r") as file:
        data = file.read()
    return data


# Patch the OpenAI client
client = instructor.from_openai(OpenAI(), mode=instructor.Mode.JSON)

file = "scraped_data/plaid/careers_openings_engineering_san_francisco_data_engineer_data_engineering.txt"
# Extract structured data from natural language
role = client.chat.completions.create(
    model="gpt-3.5-turbo",
    response_model=RoleBase,
    messages=[{"role": "user", "content": load_html(file)}],
)

print(role)
