from sqlalchemy.orm import Session
from typing import List, Dict
from app.connectors.jira_client import fetch_jira_issues
from app.db.crud import create_requirement


def ingest_jira_data(
    db: Session,
    jira_url: str = None,
    username: str = None,
    api_token: str = None,
    jql: str = "project IS NOT EMPTY"
) -> Dict[str, int]:
    """
    Ingest Jira issues into the database as requirements
    
    Args:
        db: Database session
        jira_url: Jira instance URL
        username: Jira username/email
        api_token: Jira API token
        jql: JQL query to filter issues
        
    Returns:
        Dictionary with ingestion statistics
    """
    try:
        # Fetch issues from Jira
        issues = fetch_jira_issues(
            jira_url=jira_url,
            username=username,
            api_token=api_token,
            jql=jql
        )
        
        ingested_count = 0
        failed_count = 0
        
        # Loop through issues and save as requirements
        for issue in issues:
            try:
                # Extract issue data
                fields = issue.get("fields", {})
                key = issue.get("key", "")
                summary = fields.get("summary", "")
                description = fields.get("description", "")
                
                # Create title from key and summary
                title = f"{key}: {summary}"
                
                # Save to database using CRUD
                create_requirement(db, title=title, description=str(description))
                ingested_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"Failed to ingest issue {issue.get('key', 'unknown')}: {str(e)}")
        
        return {
            "total_fetched": len(issues),
            "ingested": ingested_count,
            "failed": failed_count
        }
        
    except Exception as e:
        raise Exception(f"Failed to ingest Jira data: {str(e)}")
