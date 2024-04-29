

uvicorn main:app --reload

#workflow: 
1. Change Model or code 
2. Commit to branch
3. generate migrations file: 
alembic revision --autogenerate -m "Git Branch Name"
4. Review Revision generated in versions
5. run upgrade on test database


#TODO: 
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



Helpful Resources: 
fastUi: https://github.com/pydantic/FastUI
* fastui and fastapi: https://www.youtube.com/watch?v=eBWrnSyN2iw

pydantic: https://docs.pydantic.dev/2.7/api/validate_call/

sqlModel: https://sqlmodel.tiangolo.com/features/?h=validation#based-on-pydantic

fastAPI: https://fastapi.tiangolo.com/

alembic: https://alembic.sqlalchemy.org/en/latest/
* alembic best practices: https://thinhdanggroup.github.io/alembic-python/
* fastapi and alembic: https://www.youtube.com/watch?v=zTSmvUVbk8M