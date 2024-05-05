from fastapi import FastAPI
from api.learning import band, album, special
from api.scraper import url
from api.aifunctions import parseRole

from api.auth import privateEndpointExample, user


print("\n access docs at: http://127.0.0.1:8000/docs \n")
app = FastAPI(
    title="Hello World",
    description="Learning to code",
    version="0.0.1",
    contact={"name": "Jordan", "email": "jckail13@gmail.com"},
    license_info={"name": "MIT"},
)

app.include_router(privateEndpointExample.router)
app.include_router(parseRole.router)
app.include_router(band.router)
app.include_router(album.router)
app.include_router(user.router)
app.include_router(special.router)
app.include_router(url.router)
