from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


Base = declarative_base()


class AnalysisTask(Base):  # type: ignore[valid-type,misc]
    __tablename__ = "analysis_tasks"

    id = Column(String, primary_key=True)
    repo_url = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    status = Column(String, default=TaskStatus.PENDING)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    results = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)


class PRAnalysisRequest(BaseModel):
    repo_url: str
    pr_number: int
    github_token: str


class CodeIssue(BaseModel):
    type: str
    line: int
    description: str
    suggestion: str
    severity: str = "medium"


class FileAnalysis(BaseModel):
    name: str
    path: str
    issues: List[CodeIssue]
    lines_analyzed: int


class AnalysisSummary(BaseModel):
    total_files: int
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    languages_detected: List[str]


class AnalysisResults(BaseModel):
    files: List[FileAnalysis]
    summary: AnalysisSummary
    recommendations: List[str]


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    results: Optional[AnalysisResults] = None
    error_message: Optional[str] = None
