import requests
import base64
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import logging
import chardet

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.base_url = "https://api.github.com"
        self.session = requests.Session()

        if self.token:
            self.session.headers.update(
                {
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                }
            )

    def parse_repo_url(self, repo_url: str) -> Tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repo name."""
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) < 2:
            raise ValueError("Invalid GitHub repository URL")

        owner = path_parts[0]
        repo = path_parts[1].replace(".git", "")

        return owner, repo

    def get_pull_request(self, repo_url: str, pr_number: int) -> Dict:
        """Get pull request information."""
        owner, repo = self.parse_repo_url(repo_url)

        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self.session.get(url)
        response.raise_for_status()

        return response.json()

    def get_pull_request_files(self, repo_url: str, pr_number: int) -> List[Dict]:
        """Get files changed in a pull request."""
        owner, repo = self.parse_repo_url(repo_url)

        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = self.session.get(url)
        response.raise_for_status()

        return response.json()

    def get_file_content(self, repo_url: str, file_path: str, ref: str = "main") -> str:
        """Get content of a specific file."""
        owner, repo = self.parse_repo_url(repo_url)

        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{file_path}"
        params = {"ref": ref}

        response = self.session.get(url, params=params)
        response.raise_for_status()

        content_data = response.json()

        if content_data.get("encoding") == "base64":
            decoded_bytes = base64.b64decode(content_data["content"])
            detected = chardet.detect(decoded_bytes)
            encoding = detected["encoding"] or "utf-8"  # fallback to utf-8
            content = decoded_bytes.decode(encoding, errors="replace")  # or "ignore"
        else:
            content = content_data["content"]

        return content

    def get_pull_request_diff(self, repo_url: str, pr_number: int) -> str:
        """Get the diff for a pull request."""
        owner, repo = self.parse_repo_url(repo_url)

        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {"Accept": "application/vnd.github.v3.diff"}

        response = self.session.get(url, headers=headers)
        response.raise_for_status()

        return response.text

    def detect_language(self, filename: str) -> str:
        """Detect programming language from filename."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".php": "php",
            ".rb": "ruby",
            ".go": "go",
            ".rs": "rust",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".sql": "sql",
            ".sh": "bash",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".less": "less",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".md": "markdown",
            ".txt": "text",
        }

        for ext, lang in extension_map.items():
            if filename.lower().endswith(ext):
                return lang

        return "text"
