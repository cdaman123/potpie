import pytest
from unittest.mock import Mock, patch
from potpie.github_client import GitHubClient  # type: ignore[import-untyped]


def test_parse_repo_url():
    """Test parsing GitHub repository URLs."""
    client = GitHubClient()

    # Test HTTPS URL
    owner, repo = client.parse_repo_url("https://github.com/owner/repo")
    assert owner == "owner"
    assert repo == "repo"

    # Test HTTPS URL with .git
    owner, repo = client.parse_repo_url("https://github.com/owner/repo.git")
    assert owner == "owner"
    assert repo == "repo"

    # Test invalid URL
    with pytest.raises(ValueError):
        client.parse_repo_url("invalid-url")


def test_detect_language():
    """Test language detection from filenames."""
    client = GitHubClient()

    assert client.detect_language("main.py") == "python"
    assert client.detect_language("app.js") == "javascript"
    assert client.detect_language("component.tsx") == "typescript"
    assert client.detect_language("Main.java") == "java"
    assert client.detect_language("main.cpp") == "cpp"
    assert client.detect_language("style.css") == "css"
    assert client.detect_language("config.yml") == "yaml"
    assert client.detect_language("unknown.xyz") == "text"


@patch("requests.Session.get")
def test_get_pull_request(mock_get):
    """Test getting pull request information."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = {
        "number": 123,
        "title": "Test PR",
        "state": "open",
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = GitHubClient()
    result = client.get_pull_request("https://github.com/owner/repo", 123)

    assert result["number"] == 123
    assert result["title"] == "Test PR"
    assert result["state"] == "open"

    # Verify the correct URL was called
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert "repos/owner/repo/pulls/123" in args[0]


@patch("requests.Session.get")
def test_get_pull_request_files(mock_get):
    """Test getting files from a pull request."""
    # Mock response
    mock_response = Mock()
    mock_response.json.return_value = [
        {"filename": "main.py", "status": "modified", "additions": 10, "deletions": 5}
    ]
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = GitHubClient()
    result = client.get_pull_request_files("https://github.com/owner/repo", 123)

    assert len(result) == 1
    assert result[0]["filename"] == "main.py"
    assert result[0]["status"] == "modified"

    # Verify the correct URL was called
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert "repos/owner/repo/pulls/123/files" in args[0]


@patch("requests.Session.get")
def test_get_file_content(mock_get):
    """Test getting file content."""
    import base64

    # Mock response
    content = "print('Hello, World!')"
    encoded_content = base64.b64encode(content.encode()).decode()

    mock_response = Mock()
    mock_response.json.return_value = {"content": encoded_content, "encoding": "base64"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = GitHubClient()
    result = client.get_file_content("https://github.com/owner/repo", "main.py")

    assert result == content

    # Verify the correct URL was called
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert "repos/owner/repo/contents/main.py" in args[0]


@patch("requests.Session.get")
def test_get_pull_request_diff(mock_get):
    """Test getting pull request diff."""
    # Mock response
    diff_content = """diff --git a/main.py b/main.py
index 1234567..abcdefg 100644
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 def main():
+    print("Hello, World!")
     pass
"""

    mock_response = Mock()
    mock_response.text = diff_content
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    client = GitHubClient()
    result = client.get_pull_request_diff("https://github.com/owner/repo", 123)

    assert result == diff_content

    # Verify the correct URL and headers were used
    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert "repos/owner/repo/pulls/123" in args[0]
    assert kwargs["headers"]["Accept"] == "application/vnd.github.v3.diff"


def test_github_client_with_token():
    """Test GitHubClient initialization with token."""
    token = "test_token"
    client = GitHubClient(token=token)

    assert client.token == token
    assert "Authorization" in client.session.headers
    assert client.session.headers["Authorization"] == f"token {token}"


def test_github_client_without_token():
    """Test GitHubClient initialization without token."""
    client = GitHubClient()

    assert client.token is None
    assert "Authorization" not in client.session.headers
