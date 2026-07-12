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
    railway_token = os.environ.get('RAILWAY_TOKEN', '')
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

      - name: Deploy to Railway via API
        id: deploy
        run: |
          echo "Creating Railway project and deploying..."
          
          REPO_NAME=$(echo "${{{{ github.repository }}}}" | cut -d'/' -f2)
          
          # Create project via Railway GraphQL API
          RESPONSE=$(curl -s -X POST https://backboard.railway.app/graphql/v2 \\
            -H "Authorization: Bearer {railway_token}" \\
            -H "Content-Type: application/json" \\
            -d "{{
              \\"query\\": \\"mutation {{ projectCreate(input: {{ name: \\\\\\"$REPO_NAME-${{{{ github.event.client_payload.environment }}}}\\\\\\", defaultEnvironmentName: \\\\\\"${{{{ github.event.client_payload.environment }}}}\\\\\\" }}) {{ id environments {{ edges {{ node {{ id name }} }} }} }} }}\\"
            }}")
          
          echo "Railway response: $RESPONSE"
          PROJECT_ID=$(echo $RESPONSE | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['projectCreate']['id'])" 2>/dev/null || echo "")
          ENV_ID=$(echo $RESPONSE | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['projectCreate']['environments']['edges'][0]['node']['id'])" 2>/dev/null || echo "")
          
          if [ -z "$PROJECT_ID" ]; then
            echo "Failed to create Railway project"
            exit 1
          fi
          
          echo "Project ID: $PROJECT_ID"
          echo "Environment ID: $ENV_ID"
          
          # Create service from GitHub repo
          SERVICE_RESPONSE=$(curl -s -X POST https://backboard.railway.app/graphql/v2 \\
            -H "Authorization: Bearer {railway_token}" \\
            -H "Content-Type: application/json" \\
            -d "{{
              \\"query\\": \\"mutation {{ serviceCreate(input: {{ projectId: \\\\\\"$PROJECT_ID\\\\\\", source: {{ repo: \\\\\\"${{{{ github.repository }}}}\\\\\\" }} }}) {{ id }} }}\\"
            }}")
          
          echo "Service response: $SERVICE_RESPONSE"
          SERVICE_ID=$(echo $SERVICE_RESPONSE | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['data']['serviceCreate']['id'])" 2>/dev/null || echo "")
          
          # Wait for deployment
          sleep 30
          
          # Get deployment URL
          DOMAIN_RESPONSE=$(curl -s -X POST https://backboard.railway.app/graphql/v2 \\
            -H "Authorization: Bearer {railway_token}" \\
            -H "Content-Type: application/json" \\
            -d "{{
              \\"query\\": \\"mutation {{ serviceDomainCreate(input: {{ serviceId: \\\\\\"$SERVICE_ID\\\\\\", environmentId: \\\\\\"$ENV_ID\\\\\\" }}) {{ domain }} }}\\"
            }}")
          
          DEPLOY_URL=$(echo $DOMAIN_RESPONSE | python3 -c "import sys,json; d=json.load(sys.stdin); print('https://' + d['data']['serviceDomainCreate']['domain'])" 2>/dev/null || echo "https://railway.app/project/$PROJECT_ID")
          
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
