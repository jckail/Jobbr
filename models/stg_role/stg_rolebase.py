from typing import Optional, List

from models.mixins import BaseMixin
from sqlalchemy.dialects import postgresql
from sqlmodel import (
    Field,
    SQLModel,
    Column,
    String,
)


##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think
class Stg_RoleBase(BaseMixin, SQLModel):
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
