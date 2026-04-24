import requests
from typing import List, Dict, Optional
import os


def fetch_jira_issues(
    jira_url: str = None,
    username: str = None,
    api_token: str = None,
    jql: str = "project IS NOT EMPTY",
    max_results: int = 100
) -> List[Dict]:
    """
    Fetch issues from Jira API
    
    Args:
        jira_url: Jira instance URL (e.g., https://your-domain.atlassian.net)
        username: Jira username/email
        api_token: Jira API token
        jql: JQL query to filter issues
        max_results: Maximum number of results to return
        
    Returns:
        List of Jira issues as dictionaries
    """
    # Use environment variables as defaults
    jira_url = jira_url or os.getenv("JIRA_URL")
    username = username or os.getenv("JIRA_USERNAME")
    api_token = api_token or os.getenv("JIRA_API_TOKEN")
    
    if not all([jira_url, username, api_token]):
        raise ValueError("Jira credentials are required (URL, username, API token)")
    
    # Construct API endpoint
    api_url = f"{jira_url}/rest/api/3/search"
    
    # Set up authentication and headers
    auth = (username, api_token)
    headers = {
        "Accept": "application/json"
    }
    
    # Query parameters
    params = {
        "jql": jql,
        "maxResults": max_results,
        "fields": "summary,description,status,issuetype,key"
    }
    
    try:
        response = requests.get(api_url, auth=auth, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        issues = data.get("issues", [])
        
        return issues
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch Jira issues: {str(e)}")
