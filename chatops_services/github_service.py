import requests
import os
import base64
import time


def get_headers():
    """Get headers fresh every time — reads env vars at call time."""
    token = os.environ.get("GITHUB_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
def get_workflow_content():
    """Generate workflow content with current env var values."""
    webhook_url    = os.environ.get("CHATOPS_WEBHOOK_URL", "")
    webhook_secret = os.environ.get("CHATOPS_WEBHOOK_SECRET", "")

    return f"""name: ChatOps Deployment

on:
  repository_dispatch:
    types: [chatops-deploy]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Show Deployment Info
        run: |
          echo "Deploying to ${{{{ github.event.client_payload.environment }}}}"
          echo "Deployment ID: ${{{{ github.event.client_payload.deployment_id }}}}"
          echo "Deploy successful!"

      - name: Notify Backend - SUCCESS
        if: success()
        run: |
          curl -X POST {webhook_url}/webhook/github \\
            -H "Content-Type: application/json" \\
            -H "X-Webhook-Secret: {webhook_secret}" \\
            -d "{{\\\"deployment_id\\\": \\\"${{{{ github.event.client_payload.deployment_id }}}}\\\", \\\"status\\\": \\\"SUCCESS\\\", \\\"environment\\\": \\\"${{{{ github.event.client_payload.environment }}}}\\\", \\\"run_url\\\": \\\"https://github.com/${{{{ github.repository }}}}/actions/runs/${{{{ github.run_id }}}}\\\"}}"

      - name: Notify Backend - FAILED
        if: failure()
        run: |
          curl -X POST {webhook_url}/webhook/github \\
            -H "Content-Type: application/json" \\
            -H "X-Webhook-Secret: {webhook_secret}" \\
            -d "{{\\\"deployment_id\\\": \\\"${{{{ github.event.client_payload.deployment_id }}}}\\\", \\\"status\\\": \\\"FAILED\\\", \\\"environment\\\": \\\"${{{{ github.event.client_payload.environment }}}}\\\", \\\"run_url\\\": \\\"https://github.com/${{{{ github.repository }}}}/actions/runs/${{{{ github.run_id }}}}\\\"}}"
"""


def parse_repo(repo_url: str):
    """Parse owner and repo name from GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1]


def ensure_workflow_exists(owner: str, repo: str):
    """
    Checks if workflow exists in target repo.
    If not, creates it automatically.
    """
    headers   = get_headers()
    file_path = ".github/workflows/chatops-deploy.yml"
    url       = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"

    # Check if workflow already exists
    check = requests.get(url, headers=headers)

    if check.status_code == 200:
        print(f"Workflow already exists in {owner}/{repo}")
        return {"success": True, "created": False}

    # Workflow missing - create it automatically
    print(f"Creating workflow in {owner}/{repo}...")
    content_encoded = base64.b64encode(
        get_workflow_content().encode()
    ).decode()

    create = requests.put(
        url,
        headers=headers,
        json={
            "message": "chore: add ChatOps deployment workflow [auto-created]",
            "content": content_encoded
        }
    )

    if create.status_code == 201:
        print(f"Workflow created successfully in {owner}/{repo}")
        return {"success": True, "created": True}
    else:
        print(f"Failed to create workflow: {create.text}")
        return {"success": False, "error": create.text}


def trigger_dispatch(owner: str, repo: str, environment: str, deployment_id: int):
    """Triggers the GitHub Actions workflow."""
    headers  = get_headers()
    url      = f"https://api.github.com/repos/{owner}/{repo}/dispatches"

    response = requests.post(
        url,
        headers=headers,
        json={
            "event_type": "chatops-deploy",
            "client_payload": {
                "environment":   environment,
                "deployment_id": str(deployment_id),
                "triggered_by":  "chatops"
            }
        }
    )

    if response.status_code == 204:
        return {"success": True}
    else:
        return {"success": False, "error": response.text}


def trigger_github_deployment(repo_url: str, environment: str, deployment_id: int):
    """
    FULL AUTOMATIC FLOW:
    1. Parse owner/repo from URL
    2. Create workflow if missing
    3. Trigger deployment

    User just types /deploy <any-github-repo> <env>
    Everything else is automatic!
    """
    try:
        # Step 1 - Parse repo URL
        owner, repo = parse_repo(repo_url)
        print(f"Processing deployment for {owner}/{repo}")

        # Step 2 - Auto create workflow if missing
        workflow_result = ensure_workflow_exists(owner, repo)
        if not workflow_result["success"]:
            return {
                "success": False,
                "error": f"Could not setup workflow: {workflow_result['error']}"
            }

        # Step 3 - Wait briefly if workflow was just created
        if workflow_result.get("created"):
            print("Workflow just created, waiting 5 seconds...")
            time.sleep(5)

        # Step 4 - Trigger the deployment
        result = trigger_dispatch(owner, repo, environment, deployment_id)
        return result
    
    except Exception as e:
        return {"success": False, "error": str(e)}