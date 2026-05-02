from pydantic import BaseModel


class StatusCounts(BaseModel):
    pending: int = 0
    ready: int = 0
    error: int = 0


class SubjectCount(BaseModel):
    subject: str
    count: int


class GradeCount(BaseModel):
    grade: str
    count: int


class DailyCount(BaseModel):
    date: str  # ISO date string YYYY-MM-DD
    count: int


class LessonPlanAnalytics(BaseModel):
    total: int
    by_status: StatusCounts
    by_subject: list[SubjectCount]
    by_grade: list[GradeCount]
    daily_last_30: list[DailyCount]


class ExamGenerationAnalytics(BaseModel):
    total: int
    by_status: StatusCounts
    by_subject: list[SubjectCount]
    by_grade: list[GradeCount]
    daily_last_30: list[DailyCount]


class AnalyticsResponse(BaseModel):
    lesson_plans: LessonPlanAnalytics
    exam_generations: ExamGenerationAnalytics
