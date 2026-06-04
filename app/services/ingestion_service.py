from sqlalchemy.orm import Session
from typing import List, Dict
from app.connectors.jira_client import fetch_jira_issues
from app.connectors.confluence_client import fetch_confluence_pages
from app.connectors.testcase_loader import read_testcases_from_csv
from app.db.crud import create_requirement, create_testcase, bulk_create_requirements, bulk_create_testcases


def ingest_jira_data(
    db: Session,
    jira_url: str = None,
    username: str = None,
    api_token: str = None,
    jql: str = "project IS NOT EMPTY",
    use_bulk: bool = True
) -> Dict[str, int]:
    """
    Ingest Jira issues into the database as requirements
    
    Args:
        db: Database session
        jira_url: Jira instance URL
        username: Jira username/email
        api_token: Jira API token
        jql: JQL query to filter issues
        use_bulk: Whether to use bulk insert (recommended for >10 issues)
        
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
        
        if use_bulk and len(issues) > 5:
            # Use bulk operation for better performance
            requirements_data = []
            failed_count = 0
            
            for issue in issues:
                try:
                    # Extract issue data
                    fields = issue.get("fields", {})
                    key = issue.get("key", "")
                    summary = fields.get("summary", "")
                    description = fields.get("description", "")
                    
                    # Create title from key and summary
                    title = f"{key}: {summary}"
                    requirements_data.append((title, str(description)))
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Failed to parse issue {issue.get('key', 'unknown')}: {str(e)}")
            
            # Bulk insert all requirements
            created = bulk_create_requirements(db, requirements_data)
            ingested_count = len(created)
            
            return {
                "total_fetched": len(issues),
                "ingested": ingested_count,
                "failed": failed_count
            }
        else:
            # Use individual inserts for small batches
            ingested_count = 0
            failed_count = 0
            
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
    space_key: str = None,
    use_bulk: bool = True
) -> Dict[str, int]:
    """
    Ingest Confluence pages into the database as requirements
    
    Args:
        db: Database session
        confluence_url: Confluence instance URL
        username: Confluence username/email
        api_token: Confluence API token
        space_key: Confluence space key to filter pages
        use_bulk: Whether to use bulk insert (recommended for >10 pages)
        
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
        
        if use_bulk and len(pages) > 5:
            # Use bulk operation for better performance
            requirements_data = []
            failed_count = 0
            
            for page in pages:
                try:
                    # Extract page data
                    page_id = page.get("id", "")
                    title = page.get("title", "")
                    
                    # Extract body content
                    body = page.get("body", {}).get("storage", {}).get("value", "")
                    
                    # Create description from page ID and body
                    description = f"Confluence Page ID: {page_id}\n\n{body}"
                    requirements_data.append((title, description))
                    
                except Exception as e:
                    failed_count += 1
                    print(f"Failed to parse page {page.get('title', 'unknown')}: {str(e)}")
            
            # Bulk insert all requirements
            created = bulk_create_requirements(db, requirements_data)
            ingested_count = len(created)
            
            return {
                "total_fetched": len(pages),
                "ingested": ingested_count,
                "failed": failed_count
            }
        else:
            # Use individual inserts for small batches
            ingested_count = 0
            failed_count = 0
            
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


def ingest_testcases_data(
    db: Session,
    file_path: str
) -> Dict[str, int]:
    """
    Ingest test cases from a CSV file into the database
    
    Args:
        db: Database session
        file_path: Path to the CSV file containing test cases
        
    Returns:
        Dictionary with ingestion statistics
    """
    try:
        # Read test cases from CSV
        testcases = read_testcases_from_csv(file_path)
        
        ingested_count = 0
        failed_count = 0
        
        # Loop through test cases and save to database
        for testcase in testcases:
            try:
                # Extract test case data
                name = testcase.get("name", "")
                steps = testcase.get("steps", "")
                description = testcase.get("description", "")
                expected_result = testcase.get("expected_result", "")
                
                # Combine steps, description, and expected result
                full_steps = f"{description}\n\nSteps:\n{steps}\n\nExpected Result:\n{expected_result}"
                
                # Save to database using CRUD
                create_testcase(db, name=name, steps=full_steps)
                ingested_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"Failed to ingest test case {testcase.get('name', 'unknown')}: {str(e)}")
        
        return {
            "total_fetched": len(testcases),
            "ingested": ingested_count,
            "failed": failed_count
        }
        
    except Exception as e:
        raise Exception(f"Failed to ingest test cases: {str(e)}")

