from pydantic import BaseModel

class AdminLogin(BaseModel):
    username: str
    password: str

class AdminOut(BaseModel):
    id: str
    username: str