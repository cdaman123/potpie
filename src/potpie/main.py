from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from potpie.database import get_db
from potpie.models import (
    PRAnalysisRequest,
    AnalysisTask,
    TaskStatus,
)
from potpie.tasks import analyze_pull_request_task
from potpie.config import settings
import uuid
import structlog
from potpie.celery_app import celery_app


structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Potpie AI Code Review",
    description="Potpie github pull request analysis API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return "Hi Potpie"


@app.post("/analyze-pr", response_model=dict)
async def analyze_pull_request(
    request: PRAnalysisRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    """
    Start analysis of a GitHub pull request.

    Returns a task ID that can be used to check status and retrieve results.
    """
    try:
        task_id = str(uuid.uuid4())

        db_task = AnalysisTask(
            id=task_id,
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            status=TaskStatus.PENDING,
        )
        db.add(db_task)
        db.commit()

        analyze_pull_request_task.delay(
            task_id=task_id,
            repo_url=request.repo_url,
            pr_number=request.pr_number,
            github_token=request.github_token,
        )

        logger.info(
            "Started PR analysis task",
            task_id=task_id,
            repo_url=request.repo_url,
            pr_number=request.pr_number,
        )

        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Analysis started. Use the task_id to check status and retrieve results.",
            "status_url": f"/status/{task_id}",
            "results_url": f"/results/{task_id}",
        }

    except Exception as e:
        logger.error("Failed to start PR analysis", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to start analysis: {str(e)}"
        )


@app.get("/status/{task_id}", response_model=dict)
async def get_task_status(task_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Get the status of an analysis task.
    """
    try:
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        celery_task = celery_app.AsyncResult(task_id)  # type: ignore[call-arg]

        response = {
            "task_id": task_id,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "repo_url": task.repo_url,
            "pr_number": task.pr_number,
        }

        if celery_task.state == "PROGRESS":
            response["progress"] = celery_task.info

        if task.status == TaskStatus.FAILED and task.error_message:
            response["error_message"] = task.error_message

        if task.status == TaskStatus.COMPLETED and task.results:
            summary = task.results.get("summary", {})
            response["summary"] = {
                "total_files": summary.get("total_files", 0),
                "total_issues": summary.get("total_issues", 0),
                "critical_issues": summary.get("critical_issues", 0),
                "high_issues": summary.get("high_issues", 0),
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get task status", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        )


@app.get("/results/{task_id}", response_model=dict)
async def get_task_results(task_id: str, db: Session = Depends(get_db)):
    """
    Get the results of a completed analysis task.
    """
    try:
        # Get task from database
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.status == TaskStatus.PENDING:
            raise HTTPException(
                status_code=202,
                detail="Task is still pending. Check status endpoint for updates.",
            )

        if task.status == TaskStatus.PROCESSING:
            raise HTTPException(
                status_code=202,
                detail="Task is still processing. Check status endpoint for updates.",
            )

        if task.status == TaskStatus.FAILED:
            raise HTTPException(
                status_code=500,
                detail=f"Task failed: {task.error_message or 'Unknown error'}",
            )

        if not task.results:
            raise HTTPException(status_code=404, detail="Results not available")

        return {
            "task_id": task_id,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "results": task.results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get task results", task_id=task_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get task results: {str(e)}"
        )


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error("Internal server error", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "potpie.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
