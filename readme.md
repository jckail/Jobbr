# Jobbr: Agentic AI-Driven Tech Job Matching Application

JobScraperAI is a Python-based web application designed to scrape the web for job postings at tech companies and intelligently match those postings to candidates' resumes using state-of-the-art AI models. The application utilizes AI-based parsing and data transformation to convert raw HTML job postings into structured data formats that can be easily compared against a candidate's profile.

## Features

### 1. AI-Driven Job Parsing
- Utilizes Large Language Models (LLMs) like GPT-4 and Anthropic's Claude to parse job postings.
- Converts HTML job postings into structured JSON formats with fields like:
  - `company_name`
  - `title`
  - `description`
  - `location`
  - `requirements`
  - `benefits`
  - `salary`
  
### 2. Resume Matching
- Matches parsed job descriptions to a candidate's resume using NLP-based techniques.
- Identifies the best-fitting jobs by analyzing skill sets, experience, and keywords from resumes.
  
### 3. Database Integration
- Uses SQLModel (based on Pydantic) and SQLAlchemy to store parsed job postings and matched candidate information in a relational database.
- Includes functionality to migrate, store, and manage job and candidate data seamlessly.

### 4. Supabase Integration
- Uploads and stores processed job postings in Supabase.
- Supports authentication and session management for user interaction logging.

### 5. Docker Support
- Contains `docker-compose.yml` for easy setup of the development environment.
- Streamlines containerized deployment and testing.

### 6. Modular API Design
- Organized into API modules for scraping, authentication, database interaction, and AI integration.
- FastAPI is used to serve the web API, providing efficient and scalable endpoints for interaction.

### 7. Extensible Authentication
- (In-progress) Aims to include user authentication via token-based or session-based systems.
- Allows tracking user interactions and logging their actions for analytics.

### 8. Testing Suite
- Contains a variety of test scripts to verify the functionality of individual components.
- Includes both unit and integration tests to ensure the stability and accuracy of the scraping and parsing logic.

## Directory Structure

- **ai/**: Contains AI models and parsers, including methods to parse job postings from HTML using GPT-4 and Claude.
- **api/**: Modular API subdirectories for scraping, authentication, Supabase integration, etc.
- **auth/**: Utilities for handling user authentication.
- **testingStuff/**: Test scripts for parsing, AI model interaction, and data processing.
- **models/**: Likely contains Pydantic/SQLModel database models for job postings and resumes.
- **migrations/**: Alembic migrations for database schema updates.
- **main.py**: Entry point for the web application.
- **db.py**: Handles database initialization and connection setup.
- **docker-compose.yml**: Configuration file for containerizing the app in a Docker environment.
- **requirements.txt**: List of Python dependencies.

## Key Files and Functions

- **ai/htmlParsers.py**: Contains functions such as `parseHTMLgpt4` and `parseHTMLClaud3` for converting HTML job postings to structured JSON using AI models.
- **testingStuff/tempCodeRunnerFile.py**: A test script that includes `parse_html`, which filters text content from HTML files.
- **testingStuff/aiRefac.py**: Defines the `RoleBase` class using Pydantic, representing the structure of job roles.
- **supaBasetest.py**: Demonstrates how to upload parsed job postings to Supabase storage.
- **testingStuff/stg_role.py**: Script responsible for processing HTML job postings and interacting with AI models.
- **testingStuff/sampleChain.py**: Script for loading job data from CSV files and interacting with OpenAI's API.
- **testingStuff/tutorial.py**: Demonstrates LangChain integration with OpenAI for document embedding and similarity analysis.


#workflow: 
1. Change Model or code 
2. Commit to branch
3. generate migrations file: 
alembic revision --autogenerate -m "Git Branch Name"
4. Review Revision generated in versions
5. run upgrade on test database


### Helpful Resources: 
fastUi: https://github.com/pydantic/FastUI
* fastui and fastapi: https://www.youtube.com/watch?v=eBWrnSyN2iw

pydantic: https://docs.pydantic.dev/2.7/api/validate_call/

sqlModel: https://sqlmodel.tiangolo.com/features/?h=validation#based-on-pydantic

fastAPI: https://fastapi.tiangolo.com/

alembic: https://alembic.sqlalchemy.org/en/latest/
* alembic best practices: https://thinhdanggroup.github.io/alembic-python/
* fastapi and alembic: https://www.youtube.com/watch?v=zTSmvUVbk8M



### TODO: 
0. Add in authenticaion 
   1. Tie to user session
   2. Log actions in session
1. Figure out poetry
2. setup correct docker compose for app deployment
3. understand session tracking
4. create authentication 
5. create fast ui for barebones
6. create cli tool for easy dev
7. figure out testing files
8. migrate over code from Jobbr repo
