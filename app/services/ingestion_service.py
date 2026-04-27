from sqlalchemy.orm import Session
from typing import List, Dict
from app.connectors.jira_client import fetch_jira_issues
from app.connectors.confluence_client import fetch_confluence_pages
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


def ingest_confluence_data(
    db: Session,
    confluence_url: str = None,
    username: str = None,
    api_token: str = None,
    space_key: str = None
) -> Dict[str, int]:
    """
    Ingest Confluence pages into the database as requirements
    
    Args:
        db: Database session
        confluence_url: Confluence instance URL
        username: Confluence username/email
        api_token: Confluence API token
        space_key: Confluence space key to filter pages
        
    Returns:
        Dictionary with ingestion statistics
    """
    try:
        # Fetch pages from Confluence
        pages = fetch_confluence_pages(
            confluence_url=confluence_url,
            username=username,
            api_token=api_token,
            space_key=space_key
        )
        
        ingested_count = 0
        failed_count = 0
        
        # Loop through pages and save as requirements
        for page in pages:
            try:
                # Extract page data
                page_id = page.get("id", "")
                title = page.get("title", "")
                
                # Extract body content
                body = page.get("body", {}).get("storage", {}).get("value", "")
                
                # Create description from page ID and body
                description = f"Confluence Page ID: {page_id}\n\n{body}"
                
                # Save to database using CRUD
                create_requirement(db, title=title, description=description)
                ingested_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"Failed to ingest page {page.get('title', 'unknown')}: {str(e)}")
        
        return {
            "total_fetched": len(pages),
            "ingested": ingested_count,
            "failed": failed_count
        }
        
    except Exception as e:
        raise Exception(f"Failed to ingest Confluence data: {str(e)}")
