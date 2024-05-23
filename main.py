from fastapi import FastAPI
from api.learning import band, album, special
from api.scraper import url
from api.aifunctions import parseRole
from api.supabase import supaAuth
import uvicorn
from api.auth import privateEndpointExample, user
import redis.asyncio as aioredis
import asyncio
from contextlib import asynccontextmanager
from enum import Enum

redis = None

REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = "yourpasswordhere"



class QueueName(str,Enum):
    PROCESS_1 = "queue1"
    PROCESS_2 = "queue2"
    # Add other queues as needed

async def process_web_link():
    while True:
        task = await redis.lpop(QueueName.PROCESS_1)
        if task:
            print(f'Task removed and processed: {task}')
        else:
            await asyncio.sleep(5)  # Adjust the sleep time as necessary

async def open_redis_connection():
    global redis
    redis = aioredis.from_url(
        f"redis://{REDIS_HOST}:{REDIS_PORT}",
        password=REDIS_PASSWORD,
        decode_responses=True  # Automatically decode responses to Unicode
    )

async def close_redis_connection():
    await redis.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await open_redis_connection()
    asyncio.create_task(process_web_link())
    yield
    await close_redis_connection()





print("\n access docs at: http://127.0.0.1:8000/docs \n")
app = FastAPI(
    title="Hello World",
    description="Learning to code",
    version="0.0.1",
    contact={"name": "Jordan", "email": "jckail13@gmail.com"},
    license_info={"name": "MIT"},
    lifespan=lifespan
)

app.include_router(supaAuth.router)
app.include_router(privateEndpointExample.router)
app.include_router(parseRole.router)
# app.include_router(band.router)
# app.include_router(album.router)
# app.include_router(user.router)
# app.include_router(special.router)
app.include_router(url.router)


if __name__ == "__main__":
    uvicorn.run("main:app", port=8080, host="0.0.0.0", reload=True)
