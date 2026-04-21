import uuid

from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str  # client/org name


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    api_key: str  # raw key — shown once on signup; rotated on each login
    client_id: str
    name: str
    email: str
    teacher_id: uuid.UUID
    is_admin: bool
