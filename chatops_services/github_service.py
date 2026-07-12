import requests
import os
import base64

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

WEBHOOK_URL    = os.environ.get("CHATOPS_WEBHOOK_URL", "")
WEBHOOK_SECRET = os.environ.get("CHATOPS_WEBHOOK_SECRET", "")

def get_workflow_content():
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

      - name: Install Railway CLI
        run: npm install -g @railway/cli

      - name: Deploy to Railway
        id: deploy
        run: |
          echo "Deploying to Railway..."
          railway up --detach --token {os.environ.get('RAILWAY_TOKEN', '')}
          DEPLOY_URL=$(railway domain --token {os.environ.get('RAILWAY_TOKEN', '')} 2>/dev/null || echo "https://railway.app")
          echo "url=$DEPLOY_URL" >> $GITHUB_OUTPUT
          echo "Deployed to: $DEPLOY_URL"

      - name: Notify Backend - SUCCESS
        if: success()
        run: |
          curl -X POST {WEBHOOK_URL}/webhook/github \\
            -H "Content-Type: application/json" \\
            -H "X-Webhook-Secret: {WEBHOOK_SECRET}" \\
            -d "{{\\\"deployment_id\\\": \\\"${{{{ github.event.client_payload.deployment_id }}}}\\\", \\\"status\\\": \\\"SUCCESS\\\", \\\"environment\\\": \\\"${{{{ github.event.client_payload.environment }}}}\\\", \\\"url\\\": \\\"${{{{ steps.deploy.outputs.url }}}}\\\", \\\"run_url\\\": \\\"https://github.com/${{{{ github.repository }}}}/actions/runs/${{{{ github.run_id }}}}\\\"}}"

      - name: Notify Backend - FAILED
        if: failure()
        run: |
          curl -X POST {WEBHOOK_URL}/webhook/github \\
            -H "Content-Type: application/json" \\
            -H "X-Webhook-Secret: {WEBHOOK_SECRET}" \\
            -d "{{\\\"deployment_id\\\": \\\"${{{{ github.event.client_payload.deployment_id }}}}\\\", \\\"status\\\": \\\"FAILED\\\", \\\"environment\\\": \\\"${{{{ github.event.client_payload.environment }}}}\\\", \\\"run_url\\\": \\\"https://github.com/${{{{ github.repository }}}}/actions/runs/${{{{ github.run_id }}}}\\\"}}"
"""

def parse_repo(repo_url: str):
    """Parse owner and repo name from GitHub URL."""
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1]


def ensure_workflow_exists(owner: str, repo: str):
    """
    Always updates the workflow in target repo with latest version.
    """
    file_path = ".github/workflows/chatops-deploy.yml"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"

    content_encoded = base64.b64encode(
        get_workflow_content().encode()
    ).decode()

    # Check if workflow already exists (need SHA to update)
    check = requests.get(url, headers=HEADERS)

    if check.status_code == 200:
        # File exists — update it with new content
        sha = check.json()["sha"]
        print(f"Updating existing workflow in {owner}/{repo}...")
        response = requests.put(
            url,
            headers=HEADERS,
            json={
                "message": "chore: update ChatOps deployment workflow",
                "content": content_encoded,
                "sha": sha  # required for updates
            }
        )
        if response.status_code == 200:
            print(f"Workflow updated successfully in {owner}/{repo}")
            return {"success": True, "created": False, "updated": True}
        else:
            print(f"Failed to update workflow: {response.text}")
            return {"success": False, "error": response.text}
    else:
        # File doesn't exist — create it
        print(f"Creating workflow in {owner}/{repo}...")
        response = requests.put(
            url,
            headers=HEADERS,
            json={
                "message": "chore: add ChatOps deployment workflow [auto-created]",
                "content": content_encoded
            }
        )
        if response.status_code == 201:
            print(f"Workflow created in {owner}/{repo}")
            return {"success": True, "created": True}
        else:
            print(f"Failed to create workflow: {response.text}")
            return {"success": False, "error": response.text}

def trigger_dispatch(owner: str, repo: str, environment: str, deployment_id: int):
    """Triggers the GitHub Actions workflow."""
    url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"

    response = requests.post(
        url,
        headers=HEADERS,
        json={
            "event_type": "chatops-deploy",
            "client_payload": {
                "environment": environment,
                "deployment_id": str(deployment_id),
                "triggered_by": "chatops"
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
            import time
            print("Workflow just created, waiting 3 seconds...")
            time.sleep(3)

        # Step 4 - Trigger the deployment
        result = trigger_dispatch(owner, repo, environment, deployment_id)
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}
