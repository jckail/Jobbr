from supabase import create_client, Client

import fastapi
from fastapi import HTTPException
from pydantic import BaseModel
from db import supabase

tags_metadata = ["supaAuth"]
router = fastapi.APIRouter(tags=tags_metadata)


@router.post("/sign_up")
async def signup_user(email: str, password: str):
    try:
        user = supabase.auth.sign_up(credentials={"email": email, "password": password})
        return {"user": user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An error occurred: {e}")


@router.get("/sign_in")
def sign_in(email: str, password: str):
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    return res


@router.get("/sign_out")
def sign_out():
    res = supabase.auth.sign_out()
    return res


@router.post("/session")
async def get_session():
    try:
        res = supabase.auth.get_session()
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An error occurred: {e}")
