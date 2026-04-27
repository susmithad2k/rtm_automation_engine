import requests
from typing import List, Dict, Optional
import os


def fetch_confluence_pages(
    confluence_url: str = None,
    username: str = None,
    api_token: str = None,
    space_key: str = None,
    max_results: int = 100
) -> List[Dict]:
    """
    Fetch pages from Confluence API
    
    Args:
        confluence_url: Confluence instance URL (e.g., https://your-domain.atlassian.net/wiki)
        username: Confluence username/email
        api_token: Confluence API token
        space_key: Confluence space key to filter pages (optional)
        max_results: Maximum number of results to return
        
    Returns:
        List of Confluence pages as dictionaries
    """
    # Use environment variables as defaults
    confluence_url = confluence_url or os.getenv("CONFLUENCE_URL")
    username = username or os.getenv("CONFLUENCE_USERNAME")
    api_token = api_token or os.getenv("CONFLUENCE_API_TOKEN")
    
    if not all([confluence_url, username, api_token]):
        raise ValueError("Confluence credentials are required (URL, username, API token)")
    
    # Construct API endpoint
    api_url = f"{confluence_url}/rest/api/content"
    
    # Set up authentication and headers
    auth = (username, api_token)
    headers = {
        "Accept": "application/json"
    }
    
    # Query parameters
    params = {
        "type": "page",
        "limit": max_results,
        "expand": "body.storage,version,space"
    }
    
    # Add space filter if provided
    if space_key:
        params["spaceKey"] = space_key
    
    try:
        response = requests.get(api_url, auth=auth, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        pages = data.get("results", [])
        
        return pages
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch Confluence pages: {str(e)}")
