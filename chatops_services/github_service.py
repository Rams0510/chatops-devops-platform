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

def detect_project_type(owner: str, repo: str) -> str:
    """Detects project type by checking files in the repo"""
    checks = {
        "python": ["requirements.txt", "app.py", "main.py", "setup.py"],
        "node":   ["package.json", "index.js", "server.js"],
        "static": ["index.html"]
    }
    
    for lang, files in checks.items():
        for f in files:
            url = f"https://api.github.com/repos/{owner}/{repo}/contents/{f}"
            resp = requests.get(url, headers=HEADERS)
            if resp.status_code == 200:
                print(f"Detected {lang} project (found {f})")
                return lang
    
    return "unknown"


def get_dockerfile(project_type: str) -> str:
    """Returns appropriate Dockerfile based on project type"""
    if project_type == "python":
        return """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "app.py"]
"""
    elif project_type == "node":
        return """FROM node:18-slim
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 8080
CMD ["node", "index.js"]
"""
    else:
        return """FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
"""


def get_railway_config(project_type: str) -> str:
    """Returns railway.toml based on project type"""
    if project_type == "python":
        return """[build]
builder = "nixpacks"

[deploy]
startCommand = "python app.py"
healthcheckPath = "/"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
"""
    elif project_type == "node":
        return """[build]
builder = "nixpacks"

[deploy]
startCommand = "node index.js"
healthcheckPath = "/"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
"""
    else:
        return """[build]
builder = "nixpacks"

[deploy]
startCommand = "nginx -g 'daemon off;'"
"""


def inject_deployment_files(owner: str, repo: str, project_type: str):
    """Auto-injects Dockerfile and railway.toml into target repo"""
    
    files_to_inject = {
        "Dockerfile": get_dockerfile(project_type),
        "railway.toml": get_railway_config(project_type)
    }
    
    for filename, content in files_to_inject.items():
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{filename}"
        content_encoded = base64.b64encode(content.encode()).decode()
        
        # Check if file exists
        check = requests.get(url, headers=HEADERS)
        
        if check.status_code == 200:
            # Update existing file
            sha = check.json()["sha"]
            requests.put(url, headers=HEADERS, json={
                "message": f"chore: update {filename} [chatops-auto]",
                "content": content_encoded,
                "sha": sha
            })
        else:
            # Create new file
            requests.put(url, headers=HEADERS, json={
                "message": f"chore: add {filename} [chatops-auto]",
                "content": content_encoded
            })
        
        print(f"Injected {filename} into {owner}/{repo}")

def trigger_github_deployment(repo_url: str, environment: str, deployment_id: int):
    try:
        owner, repo = parse_repo(repo_url)
        print(f"Processing deployment for {owner}/{repo}")

        # Step 1 - Detect project type
        project_type = detect_project_type(owner, repo)
        print(f"Project type: {project_type}")

        # Step 2 - Auto inject Dockerfile + railway.toml
        inject_deployment_files(owner, repo, project_type)

        # Step 3 - Create/update workflow
        workflow_result = ensure_workflow_exists(owner, repo)
        if not workflow_result["success"]:
            return {"success": False, "error": f"Could not setup workflow: {workflow_result['error']}"}

        # Step 4 - Wait if files were just created
        import time
        time.sleep(3)

        # Step 5 - Trigger deployment
        result = trigger_dispatch(owner, repo, environment, deployment_id)
        return result

    except Exception as e:
        return {"success": False, "error": str(e)}