import os
from supabase import create_client, Client

import fastapi


tags_metadata = ["supaAuth"]
router = fastapi.APIRouter(tags=tags_metadata)

url: str = "http://localhost:3000"
key: str = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE"
)

supa: Client = create_client(url, key)


# @router.get("/sign_up")
# def sign_up():
#     res = supa.auth.sign_up(email="testsupa@gmail.com", password="testsupabasenow")
#     return res.get("access_token")


# @router.get("/sign_in")
# def sign_in():

#     res = supa.auth.sign_in_with_password(
#         {"email": "testsupa@gmail.com", "password": "testsupabasenow"}
#     )
#     return res.get("access_token")
