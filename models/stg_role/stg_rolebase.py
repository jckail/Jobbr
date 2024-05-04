from typing import Optional, List

from models.mixins import BaseMixin
from sqlalchemy.dialects import postgresql
from sqlmodel import (
    Field,
    SQLModel,
    Column,
    String,
)
from uuid import UUID


# TODO: FIX INPUT TOKENS
##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think
class Stg_RoleBase(BaseMixin, SQLModel):
    """
    Pydantic Basemodel

    This data represents a job posting from a job board.


    company_name (str): The name of the company associated with the role.
    title (str): The title of the role (excluding the team).
    job_category(str): Industry standard term for the role ie software engineer, software engineering manager, accountant, product manager
    posting_date(str): when the job was posted
    employment_type(str): This field is a string. If this role is fulltime, parttime, internship, contract, contract to hire. This should be a string.
    employment_term_days(int): Length of time in days of the employment - 1 month 30 days, 4 weeks 28 days, one year 365
    description (str): A short description of the role. - under 120 characters
    team (str): The name of the team or group the role is located on - this is not the company name.
    team_description (str): A description of the team, what products they support what are the values. - under 120 characters
    expectations(str): An overview of the expectations or what the role will be doing on a daily basis. - under 120 characters
    location (List[str]): A list of locations avalible for the role IE: city,state San Francisco, California or Atlanta, Georgia.
    remote (str)): If the role allows remote work in any capacity.
    in_person (str)): If the role requires the person to go into the office or be in person.
    travel (str): The travel frequency requirements of the role.
    responsibilities (List[str]): A list of all responsibilities for the role;
    qualifications (List[str]): A list of all qualifications for the role;
    soft_skills (List[str]): The soft skills described in the role such as leadership, organization, mentorship.
    tool_experience (List[str]):  Tools or technologies used by the team not programming languages.
    programming_languages (List[str]): Programming languages the role could use IE SQL, PYTHON, Java, GO.
    technical_skills (List[str]): The technical skills required for the role .
    certifications (List[str]): Ideal certifications for the role.
    years_of_experience (int): The estimated years of experience for the role.
    prior_experience_description (str): Description of any desired previous experience.
    individual_contributor(bool): If this role is an individual contributor not directly responsible for other humans in the organization.
    people_manager (bool): If this role is a direct manager of humans in the organization - ie manager of people not a product manager.
    estimated_career_level (str): An estimation of what level at the company this is IE is a junior, midlevel, senior, manager, director or leadership role could be another value.
    education_requirement (str): This is the description of any eduction requirments for the role
    compensation_type(str): Frequency of compesation indicates salaried, hourly, etc...
    estimated_min_compensation (int): The estimated minimum compensation for the role.
    estimated_max_compensation (int): The estimated maximum compensation for the role.
    compensation_description (str): Details around the compensation for the role including a range. - under 120 characters
    unlimited_pto (bool): If the company offers unlimited PTO.
    pto_and_benefits (str): The benefits and PTO information for the role. - under 120 characters
    role_quirks (str): Anything that stands out about the role being unique or bizzare.
    ai_analysis (str): This field should be blank.
    estimated_status (str): This is a best guess if the role is still avalible based on there being a job description on the page.
    external_links (List[str]): List any URLS or hyper links found on the page
    industry (str): The industry the company is in ie "technology", "web applicaitons", "healthcare", "financial services"
    job_id (str): The unique identifier for the instance of the role often called job number or job id or role id. This often isn't shown and is tricky to spot.
    offers_401k(bool): Offers a 401k package as apart of compensation
    """

    company_name: str
    title: Optional[str]
    job_category: Optional[str]
    posting_date: Optional[str]
    employment_type: Optional[str]
    employment_term_days: Optional[int]
    description: Optional[str]
    team: Optional[str]
    team_description: Optional[str]
    expectations: Optional[str]
    location: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    remote: Optional[str]
    in_person: Optional[str]
    travel: Optional[str]
    responsibilities: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    qualifications: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    soft_skills: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    tool_experience: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    programming_languages: Optional[List[str]] = Field(
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
    individual_contributor: Optional[bool]
    people_manager: Optional[bool]
    estimated_career_level: Optional[str]
    education_requirement: Optional[str]
    compensation_type: Optional[str]
    estimated_min_compensation: Optional[int]
    estimated_max_compensation: Optional[int]
    compensation_description: Optional[str]
    unlimited_pto: Optional[bool]
    pto_and_benefits: Optional[str]  ##TODO Make this a list
    role_quirks: Optional[str]
    ai_analysis: Optional[str] = None
    estimated_status: Optional[str]
    external_links: Optional[List[str]] = Field(
        default=None, sa_column=Column(postgresql.ARRAY(String()))
    )
    industry: Optional[str]
    job_id: Optional[str]
    offers_401k: Optional[bool]

    class Config:
        """
        Pydantic model configuration.

        Configures the model settings, such as enabling ORM mode.
        """

        from_attributes = True  # if using Pydantic v2
