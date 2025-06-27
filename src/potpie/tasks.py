from celery import current_task
from potpie.celery_app import celery_app
from potpie.github_client import GitHubClient
from potpie.agents import CodeReviewAgent
from potpie.database import SessionLocal
from potpie.models import AnalysisTask, TaskStatus
import logging
import traceback

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def analyze_pull_request_task(
    self,
    task_id: str,
    repo_url: str,
    pr_number: int,
    github_token: str | None = None,
):
    """
    Celery task to analyze a pull request asynchronously.
    """
    db = SessionLocal()

    try:
        task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
        if not task:
            logger.error(f"Task {task_id} not found in database")
            return {"error": "Task not found"}

        task.status = TaskStatus.PROCESSING.value  # type: ignore[assignment]
        db.commit()

        logger.info(f"Starting analysis for PR #{pr_number} in {repo_url}")

        github_client = GitHubClient(token=github_token)

        pr_info = github_client.get_pull_request(repo_url, pr_number)
        logger.info(f"Retrieved PR info: {pr_info.get('title', 'No title')}")

        pr_files = github_client.get_pull_request_files(repo_url, pr_number)
        logger.info(f"Found {len(pr_files)} files in PR")

        files_data = []
        for file_info in pr_files:
            filename = file_info.get("filename", "")
            status = file_info.get("status", "")
            patch = file_info.get("patch", "")

            if status == "removed":
                continue

            try:
                content = ""
                if status == "added" or status == "modified":
                    content = github_client.get_file_content(
                        repo_url, filename, ref=pr_info["head"]["sha"]
                    )

                language = github_client.detect_language(filename)

                files_data.append(
                    {
                        "filename": filename,
                        "content": content,
                        "language": language,
                        "status": status,
                        "patch": patch,  # This is the diff/patch data
                        "additions": file_info.get("additions", 0),
                        "deletions": file_info.get("deletions", 0),
                        "changes": file_info.get("changes", 0),
                    }
                )

            except Exception as e:
                logger.warning(f"Failed to get content for file {filename}: {e}")
                files_data.append(
                    {
                        "filename": filename,
                        "content": "",
                        "language": "unknown",
                        "status": status,
                        "patch": patch,
                        "error": str(e),
                    }
                )

        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 30,
                "total": 100,
                "status": "Files retrieved, starting analysis...",
            },
        )

        agent = CodeReviewAgent()
        analysis_results = agent.analyze_pull_request(files_data, pr_info)

        current_task.update_state(
            state="PROGRESS",
            meta={
                "current": 90,
                "total": 100,
                "status": "Analysis complete, saving results...",
            },
        )

        results_dict = {
            "files": [
                {
                    "name": fa.name,
                    "path": fa.path,
                    "lines_analyzed": fa.lines_analyzed,
                    "issues": [
                        {
                            "type": issue.type,
                            "line": issue.line,
                            "description": issue.description,
                            "suggestion": issue.suggestion,
                            "severity": issue.severity,
                        }
                        for issue in fa.issues
                    ],
                }
                for fa in analysis_results.files
            ],
            "summary": {
                "total_files": analysis_results.summary.total_files,
                "total_issues": analysis_results.summary.total_issues,
                "critical_issues": analysis_results.summary.critical_issues,
                "high_issues": analysis_results.summary.high_issues,
                "medium_issues": analysis_results.summary.medium_issues,
                "low_issues": analysis_results.summary.low_issues,
                "languages_detected": analysis_results.summary.languages_detected,
            },
            "recommendations": analysis_results.recommendations,
            "pr_info": {
                "title": pr_info.get("title", ""),
                "number": pr_info.get("number", pr_number),
                "author": pr_info.get("user", {}).get("login", ""),
                "created_at": pr_info.get("created_at", ""),
                "updated_at": pr_info.get("updated_at", ""),
            },
        }

        task.status = TaskStatus.COMPLETED.value  # type: ignore[assignment]
        task.results = results_dict  # type: ignore[assignment]
        db.commit()

        logger.info(f"Analysis completed for task {task_id}")

        return {"status": "completed", "results": results_dict}

    except Exception as e:
        logger.error(f"Error in analyze_pull_request_task: {e}")
        logger.error(traceback.format_exc())

        try:
            task = db.query(AnalysisTask).filter(AnalysisTask.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED.value  # type: ignore[assignment]
                task.error_message = str(e)  # type: ignore[assignment]
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update task status: {db_error}")

        raise

    finally:
        db.close()
