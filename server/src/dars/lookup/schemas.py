from pydantic import BaseModel


class GradeResponse(BaseModel):
    id: int
    code: int
    display_name: str
    model_config = {"from_attributes": True}


class SubjectResponse(BaseModel):
    id: int
    code: str
    display_name: str
    model_config = {"from_attributes": True}
