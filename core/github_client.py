"""
GitHub API Client

Interacts with GitHub API for repository analysis and PR creation.

Part of Milestone 4: GitHub Code Crawler
"""

import os
import json
import logging
import base64
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub REST API."""
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub personal access token (or use GITHUB_TOKEN env var)
        """
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.api_url = "https://api.github.com"
        
        if not self.token:
            logger.warning("No GitHub token provided")
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make request to GitHub API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            data: Request body for POST/PUT
            
        Returns:
            Response data
        """
        url = f"{self.api_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "JUGGERNAUT-Code-Crawler"
        }
        
        request_data = None
        if data:
            request_data = json.dumps(data).encode('utf-8')
            headers["Content-Type"] = "application/json"
        
        req = urllib.request.Request(url, data=request_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise Exception(f"HTTP {e.code}: {error_body}")
    
    def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Get repository information.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Repository data
        """
        try:
            return self._make_request("GET", f"/repos/{owner}/{repo}")
        except Exception as e:
            logger.exception(f"Error fetching repository: {e}")
            return {}
    
    def get_contents(
        self,
        owner: str,
        repo: str,
        path: str = "",
        ref: str = "main"
    ) -> List[Dict[str, Any]]:
        """
        Get repository contents at path.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Path within repository
            ref: Branch/tag/commit
            
        Returns:
            List of files/directories
        """
        try:
            endpoint = f"/repos/{owner}/{repo}/contents/{path}"
            if ref:
                endpoint += f"?ref={ref}"
            
            result = self._make_request("GET", endpoint)
            
            # Handle single file vs directory
            if isinstance(result, dict):
                return [result]
            return result
        except Exception as e:
            logger.exception(f"Error fetching contents: {e}")
            return []
    
    def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str = "main"
    ) -> Optional[str]:
        """
        Get file content as string.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            ref: Branch/tag/commit
            
        Returns:
            File content or None
        """
        try:
            contents = self.get_contents(owner, repo, path, ref)
            if not contents:
                return None
            
            file_data = contents[0]
            if file_data.get("type") != "file":
                return None
            
            # Decode base64 content
            content_b64 = file_data.get("content", "")
            content_bytes = base64.b64decode(content_b64)
            return content_bytes.decode('utf-8')
        except Exception as e:
            logger.exception(f"Error getting file content: {e}")
            return None
    
    def list_files_recursive(
        self,
        owner: str,
        repo: str,
        path: str = "",
        ref: str = "main",
        extensions: Optional[List[str]] = None
    ) -> List[str]:
        """
        List all files recursively.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: Starting path
            ref: Branch/tag/commit
            extensions: Filter by extensions (e.g., ['.py', '.ts'])
            
        Returns:
            List of file paths
        """
        files = []
        
        try:
            contents = self.get_contents(owner, repo, path, ref)
            
            for item in contents:
                item_path = item.get("path", "")
                item_type = item.get("type", "")
                
                if item_type == "file":
                    # Check extension filter
                    if extensions:
                        if any(item_path.endswith(ext) for ext in extensions):
                            files.append(item_path)
                    else:
                        files.append(item_path)
                elif item_type == "dir":
                    # Recurse into directory
                    subfiles = self.list_files_recursive(owner, repo, item_path, ref, extensions)
                    files.extend(subfiles)
        except Exception as e:
            logger.exception(f"Error listing files: {e}")
        
        return files
    
    def create_branch(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        from_branch: str = "main"
    ) -> bool:
        """
        Create a new branch.
        
        Args:
            owner: Repository owner
            repo: Repository name
            branch_name: New branch name
            from_branch: Source branch
            
        Returns:
            True if successful
        """
        try:
            # Get SHA of source branch
            ref_data = self._make_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{from_branch}")
            sha = ref_data.get("object", {}).get("sha")
            
            if not sha:
                return False
            
            # Create new branch
            self._make_request("POST", f"/repos/{owner}/{repo}/git/refs", {
                "ref": f"refs/heads/{branch_name}",
                "sha": sha
            })
            
            return True
        except Exception as e:
            logger.exception(f"Error creating branch: {e}")
            return False
    
    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main"
    ) -> Optional[Dict[str, Any]]:
        """
        Create a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            title: PR title
            body: PR description
            head: Source branch
            base: Target branch
            
        Returns:
            PR data or None
        """
        try:
            pr_data = self._make_request("POST", f"/repos/{owner}/{repo}/pulls", {
                "title": title,
                "body": body,
                "head": head,
                "base": base
            })
            
            logger.info(f"Created PR #{pr_data.get('number')}: {title}")
            return pr_data
        except Exception as e:
            logger.exception(f"Error creating PR: {e}")
            return None
    
    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open"
    ) -> List[Dict[str, Any]]:
        """
        List pull requests.
        
        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state ('open', 'closed', 'all')
            
        Returns:
            List of PRs
        """
        try:
            return self._make_request("GET", f"/repos/{owner}/{repo}/pulls?state={state}")
        except Exception as e:
            logger.exception(f"Error listing PRs: {e}")
            return []
    
    def test_connection(self) -> bool:
        """
        Test if GitHub token is valid.
        
        Returns:
            True if connection successful
        """
        try:
            user_data = self._make_request("GET", "/user")
            logger.info(f"GitHub API connection successful. User: {user_data.get('login')}")
            return True
        except Exception as e:
            logger.error(f"GitHub API connection failed: {e}")
            return False


# Singleton instance
_github_client = None


def get_github_client() -> GitHubClient:
    """Get or create GitHub client singleton."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client


__all__ = ["GitHubClient", "get_github_client"]
