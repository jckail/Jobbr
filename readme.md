

#workflow: 
1. Change Model or code 
2. Commit to branch
3. generate migrations file: 
alembic revision --autogenerate -m "Git Branch Name"
4. Review Revision generated in versions
5. run upgrade on test database






fastUi: https://github.com/pydantic/FastUI

pydantic: https://docs.pydantic.dev/2.7/api/validate_call/

sqlModel: https://sqlmodel.tiangolo.com/features/?h=validation#based-on-pydantic

fastAPI: https://fastapi.tiangolo.com/

alembic: https://alembic.sqlalchemy.org/en/latest/