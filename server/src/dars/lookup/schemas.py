from pydantic import BaseModel


class GradeResponse(BaseModel):
    code: int
    display_name: str
    model_config = {"from_attributes": True}


class SubjectResponse(BaseModel):
    code: str
    display_name: str
    model_config = {"from_attributes": True}
