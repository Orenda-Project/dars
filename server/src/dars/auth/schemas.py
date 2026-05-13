from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str  # client/org name
    curriculum: str  # required: "NCP" or "SNC"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    api_key: str  # raw key — shown once on signup; rotated on each login
    client_id: str
    name: str
    email: str
    is_admin: bool
    curriculum: str | None = None
