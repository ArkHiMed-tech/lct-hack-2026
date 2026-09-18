from fastapi import FastAPI
from fastapi.responses import Response, FileResponse
from fastapi.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel

app = FastAPI()

class User(BaseModel):
    login: str 
    password: str
    email: str


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/users/create")
async def create_user(user: User):
    return {
        'message': f'User {user.login} created',
        'info': user.model_dump(mode = 'json')
    }