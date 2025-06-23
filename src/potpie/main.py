from fastapi import FastAPI

from src.potpie.models import PRDetails
from src.potpie.worker import process_task


app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Hello, potpie!"}

@app.post("/analyze-pr")
async def analyze_pr(details: PRDetails):
    result = process_task.apply_async(args=[details.pr_number, details.repo])
    return {"message": f"Analyzing PR #{details.pr_number} in {details.repo}"}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    return {"status": f"Status of task {task_id}"}

@app.get("/results/{task_id}")
async def get_results(task_id: str):
    return {"results for task": task_id}