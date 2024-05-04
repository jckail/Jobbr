from typing import Optional, List

from models.mixins import BaseMixin
from sqlalchemy.dialects import postgresql
from sqlmodel import (
    Field,
    SQLModel,
    Column,
    String,
)


# TODO: FIX INPUT TOKENS
##TODO create timer functions so that we can better see timing
## TODO test against langchain outputs etc its going to be better than this i think
class Stg_RoleBase(BaseMixin, SQLModel):
    """

    A Pydantic model representing a job posting, capturing essential details
    about the job role, team, and employment conditions.

    Attributes:
        company_name (str): The official name of the company offering the job.
        title (str): Specific title of the job role, not including the team name.
        job_category (Optional[str]): Standard industry designation of the role, e.g., 'software engineer'.
        posting_date (Optional[str]): Date when the job was initially posted.
        employment_type (Optional[str]): Type of employment (e.g., full-time, part-time, internship).
        employment_term_days (Optional[int]): Duration of the job term in days, where 30 days corresponds to one month.
        description (Optional[str]): Brief overview of the role, limited to 120 characters.
        team (Optional[str]): The specific team or department within the company.
        team_description (Optional[str]): Description of the team's functions and values, limited to 120 characters.
        expectations (Optional[str]): Daily expectations from the role, described in under 120 characters.
        location (Optional[List[str]]): Possible locations for the role, formatted as 'City, State'.
        remote (Optional[bool]): Whether the role permits remote work.
        in_person (Optional[bool]): Whether the role requires physical presence at the office.
        travel (Optional[str]): Expected frequency and extent of travel for the role.
        responsibilities (Optional[List[str]]): Detailed list of job responsibilities.
        qualifications (Optional[List[str]]): Required qualifications for the role.
        soft_skills (Optional[List[str]]): Non-technical skills important for the role.
        tool_experience (Optional[List[str]]): Non-programming tools and technologies used in the role.
        programming_languages (Optional[List[str]]): Programming languages relevant to the role.
        technical_skills (Optional[List[str]]): Technical skills specifically required for the role.
        certifications (Optional[List[str]]): Preferred professional certifications.
        years_of_experience (Optional[int]): Required years of professional experience.
        prior_experience_description (Optional[str]): Description of any specific previous experience desired.
        individual_contributor (Optional[bool]): If the role is for an individual contributor.
        people_manager (Optional[bool]): If the role involves managing a team.
        estimated_career_level (Optional[str]): Expected career level for the role (e.g., junior, senior).
        education_requirement (Optional[str]): Educational prerequisites for the role.
        compensation_type (Optional[str]): Basis of compensation (e.g., salaried, hourly).
        estimated_min_compensation (Optional[int]): Minimum estimated compensation for the role.
        estimated_max_compensation (Optional[int]): Maximum estimated compensation for the role.
        compensation_description (Optional[str]): Additional details about compensation, under 120 characters.
        unlimited_pto (Optional[bool]): If unlimited paid time off is offered.
        pto_and_benefits (Optional[str]): Overview of benefits and PTO, limited to 120 characters.
        role_quirks (Optional[str]): Unique or unusual aspects of the role.
        ai_analysis (Optional[str]): A summary of who might do well or like the role limited to 120 characters..
        estimated_status (Optional[str]): Assumed availability of the role based on the job posting.
        external_links (Optional[List[str]]): Relevant URLs or hyperlinks associated with the job posting.
        industry (Optional[str]): Sector the company operates in, e.g., 'technology', 'healthcare'.
        job_identifier (Optional[str]): Unique identifier for the job posting, often difficult to locate. -- this hould be a string
        offers_401k (Optional[bool]): Whether a 401k plan is part of the job's compensation package.

    Example of a populated schema as json:
    {
    "company_name": "Red Lobster",
    "title": "Server",
    "job_category": "Restaurant",
    "posting_date": "2024-04-27",
    "employment_type": "Full-time, Part-time",
    "employment_term_days": null,
    "description": "As a Server at Red Lobster, you will enhance guest experiences by offering personalized service, suggestions and pairings.",
    "team": null,
    "team_description": null,
    "expectations": "Daily tasks will include taking orders accurately, delivering hot food promptly, clearing tables, and managing transactions!",
    "location": ["Aurora, Colorado"],
    "remote": "No",
    "in_person": "Yes",
    "travel": null,
    "responsibilities": ["taking orders accurately", "delivering hot food promptly", "clearing tables", "managing transactions"],
    "qualifications": ["Must be of legal age to serve alcohol based on state requirements"],
    "soft_skills": ["Multi-tasking", "listening", "communication skills"],
    "tool_experience": ["Point of Sale systems"], // This is an inferred field since servers generally use this, not explicitly mentioned.
    "programming_languages": null,
    "technical_skills": null,
    "certifications": null,
    "years_of_experience": null,
    "prior_experience_description": null,
    "individual_contributor": true,
    "people_manager": false,
    "estimated_career_level": "Entry",
    "education_requirement": null,
    "compensation_type": "Hourly",
    "estimated_min_compensation": 11,
    "estimated_max_compensation": 25,
    "compensation_description": "$11.40 - $25.00 per hour",
    "unlimited_pto": null,
    "pto_and_benefits": null,
    "role_quirks": null,
    "ai_analysis": null,
    "estimated_status": "Active",
    "external_links": [],
    "industry": "Restaurant",
    "job_identifier": "asdfasdf23423",
    "offers_401k": null
    }


    """

    company_name: str = Field(
        description="The official name of the company offering the job."
    )
    title: Optional[str] = Field(
        default=None,
        description="Specific title of the job role, not including the team name.",
    )
    job_category: Optional[str] = Field(
        default=None,
        description="Standard industry designation of the role, e.g., 'software engineer'.",
    )
    posting_date: Optional[str] = Field(
        default=None, description="Date when the job was initially posted."
    )
    employment_type: Optional[str] = Field(
        default=None,
        description="Type of employment (e.g., full-time, part-time, internship).",
    )
    employment_term_days: Optional[int] = Field(
        default=None,
        description="Duration of the job term in days, where 30 days corresponds to one month.",
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief overview of the role, limited to 120 characters.",
    )
    team: Optional[str] = Field(
        default=None, description="The specific team or department within the company."
    )
    team_description: Optional[str] = Field(
        default=None,
        description="Description of the team's functions and values, limited to 120 characters.",
    )
    expectations: Optional[str] = Field(
        default=None,
        description="Daily expectations from the role, described in under 120 characters.",
    )
    location: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Possible locations for the role, formatted as 'City, State'.",
    )
    remote: Optional[bool] = Field(
        default=None, description="Whether the role permits remote work."
    )
    in_person: Optional[bool] = Field(
        default=None,
        description="Whether the role requires physical presence at the office.",
    )
    travel: Optional[str] = Field(
        default=None,
        description="Expected frequency and extent of travel for the role.",
    )
    responsibilities: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Detailed list of job responsibilities.",
    )
    qualifications: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Required qualifications for the role.",
    )
    soft_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Non-technical skills important for the role.",
    )
    tool_experience: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Non-programming tools and technologies used in the role.",
    )
    programming_languages: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Programming languages relevant to the role.",
    )
    technical_skills: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Technical skills specifically required for the role.",
    )
    certifications: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Preferred professional certifications.",
    )
    years_of_experience: Optional[int] = Field(
        default=None, description="Required years of professional experience."
    )
    prior_experience_description: Optional[str] = Field(
        default=None,
        description="Description of any specific previous experience desired.",
    )
    individual_contributor: Optional[bool] = Field(
        default=None, description="If the role is for an individual contributor."
    )
    people_manager: Optional[bool] = Field(
        default=None, description="If the role involves managing a team."
    )
    estimated_career_level: Optional[str] = Field(
        default=None,
        description="Expected career level for the role (e.g., junior, senior).",
    )
    education_requirement: Optional[str] = Field(
        default=None, description="Educational prerequisites for the role."
    )
    compensation_type: Optional[str] = Field(
        default=None, description="Basis of compensation (e.g., salaried, hourly)."
    )
    estimated_min_compensation: Optional[int] = Field(
        default=None, description="Minimum estimated compensation for the role."
    )
    estimated_max_compensation: Optional[int] = Field(
        default=None, description="Maximum estimated compensation for the role."
    )
    compensation_description: Optional[str] = Field(
        default=None,
        description="Additional details about compensation, under 120 characters.",
    )
    unlimited_pto: Optional[bool] = Field(
        default=None, description="If unlimited paid time off is offered."
    )
    pto_and_benefits: Optional[str] = Field(
        default=None,
        description="Overview of benefits and PTO, limited to 120 characters.",
    )
    role_quirks: Optional[str] = Field(
        default=None, description="Unique or unusual aspects of the role."
    )
    ai_analysis: Optional[str] = Field(
        default=None,
        description="A summary of who might do well or like the role limited to 120 characters.",
    )
    estimated_status: Optional[str] = Field(
        default=None,
        description="Assumed availability of the role based on the job posting.",
    )
    external_links: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(postgresql.ARRAY(String())),
        description="Relevant URLs or hyperlinks associated with the job posting.",
    )
    industry: Optional[str] = Field(
        default=None,
        description="Sector the company operates in, e.g., 'technology', 'healthcare'.",
    )
    job_identifier: Optional[str] = Field(
        default=None,
        description="Unique identifier for the job posting, often difficult to locate.",
    )
    offers_401k: Optional[bool] = Field(
        default=None,
        description="Whether a 401k plan is part of the job's compensation package.",
    )

    class Config:
        """
        Pydantic model configuration.

        Configures the model settings, such as enabling ORM mode.
        """

        from_attributes = True  # if using Pydantic v2
