import requests
import os

def trigger_github_deployment(repo_url: str, environment: str, deployment_id: int):
    """
    Fires a repository_dispatch event to trigger GitHub Actions.
    repo_url format: https://github.com/owner/repo
    """
    token = os.environ.get("GITHUB_TOKEN")
    
    # Parse owner/repo from URL
    parts = repo_url.rstrip("/").split("/")
    owner = parts[-2]
    repo  = parts[-1]

    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "event_type": "chatops-deploy",
        "client_payload": {
            "environment": environment,
            "deployment_id": str(deployment_id),
            "triggered_by": "chatops"
        }
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 204:
        return {"success": True}
    else:
        return {"success": False, "error": response.text}