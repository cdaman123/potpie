from pydantic import BaseModel

class PRDetails(BaseModel):
    repo: str
    pr_number: int