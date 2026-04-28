from pydantic import BaseModel
from typing import Optional


class JiraIngestRequest(BaseModel):
    """Request model for Jira ingestion"""
    jira_url: Optional[str] = None
    username: Optional[str] = None
    api_token: Optional[str] = None
    jql: str = "project IS NOT EMPTY"


class ConfluenceIngestRequest(BaseModel):
    """Request model for Confluence ingestion"""
    confluence_url: Optional[str] = None
    username: Optional[str] = None
    api_token: Optional[str] = None
    space_key: Optional[str] = None


class TestCasesIngestRequest(BaseModel):
    """Request model for Test Cases ingestion"""
    file_path: str
