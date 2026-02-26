import requests
import os
import base64
import json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

WORKFLOW_CONTENT = '''name: ChatOps Deployment

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
          echo "Deploying to ${{ github.event.client_payload.environment }}"
          echo "Deployment ID: ${{ github.event.client_payload.deployment_id }}"

      - name: Notify Backend - SUCCESS
        if: success()
        run: |
          curl -X POST ${{ secrets.CHATOPS_WEBHOOK_URL }}/webhook/github \\
            -H "Content-Type: application/json" \\
            -H "X-Webhook-Secret: ${{ secrets.CHATOPS_WEBHOOK_SECRET }}" \\
            -d "{\\"deployment_id\\": \\"${{ github.event.client_payload.deployment_id }}\\", \\"status\\": \\"SUCCESS\\", \\"environment\\": \\"${{ github.event.client_payload.environment }}\\", \\"run_url\\": \\"https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}\\"}"

      - name: Notify Backend - FAILED
        if: failure()
        run: |
          curl -X POST ${{ secrets.CHATOPS_WEBHOOK_URL }}/webhook/github \\
            -H "Content-Type: application/json" \\
            -H "X-Webhook-Secret: ${{ secrets.CHATOPS_WEBHOOK_SECRET }}" \\
            -d "{\\"deployment_id\\": \\"${{ github.event.client_payload.deployment_id }}\\", \\"status\\": \\"FAILED\\", \\"environment\\": \\"${{ github.event.client_payload.environment }}\\", \\"run_url\\": \\"https://github.com/${{ github.repository }}/actions/runs/${{ github.run_id }}\\"}"
'''

def ensure_workflow_exists(owner: str, repo: str):
    """
    Checks if workflow file exists in repo.
    If not, creates it automatically.
    """
    file_path = ".github/workflows/chatops-deploy.yml"
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"

    # Check if file already exists
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        print("Workflow already exists")
        return {"success": True, "created": False}

    # File doesn't exist - create it
    content_encoded = base64.b64encode(
        WORKFLOW_CONTENT.encode()
    ).decode()

    create_response = requests.put(
        url,
        headers=HEADERS,
        json={
            "message": "chore: add ChatOps deployment workflow",
            "content": content_encoded
        }
    )

    if create_response.status_code == 201:
        return {"success": True, "created": True}
    else:
        return {"success": False, "error": create_response.text}


def add_repo_secrets(owner: str, repo: str):
    """
    Adds CHATOPS_WEBHOOK_URL and CHATOPS_WEBHOOK_SECRET
    to the target repo automatically.
    Note: Requires getting repo public key first for encryption.
    """
    from nacl import encoding, public  # pip install PyNaCl

    webhook_url    = os.environ.get("RENDER_URL", "")
    webhook_secret = os.environ.get("CHATOPS_WEBHOOK_SECRET", "")

    # Get repo public key (needed to encrypt secrets)
    key_url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    key_response = requests.get(key_url, headers=HEADERS)
    key_data = key_response.json()

    public_key = public.PublicKey(
        key_data["key"].encode("utf-8"),
        encoding.Base64Encoder()
    )
    sealed_box = public.SealedBox(public_key)

    def encrypt_secret(value: str) -> str:
        encrypted = sealed_box.encrypt(value.encode("utf-8"))
        return base64.b64encode(encrypted).decode("utf-8")

    secrets_to_add = {
        "CHATOPS_WEBHOOK_URL":    webhook_url,
        "CHATOPS_WEBHOOK_SECRET": webhook_secret
    }

    for secret_name, secret_value in secrets_to_add.items():
        requests.put(
            f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}",
            headers=HEADERS,
            json={
                "encrypted_value": encrypt_secret(secret_value),
                "key_id": key_data["key_id"]
            }
        )

    return {"success": True}


def trigger_github_deployment(repo_url: str, environment: str, deployment_id: int):
    """
    Full automatic flow:
    1. Parse owner/repo from URL
    2. Create workflow if missing
    3. Add secrets if missing
    4. Trigger deployment
    """
    parts = repo_url.rstrip("/").split("/")
    owner = parts[-2]
    repo  = parts[-1]

    # Step 1: Ensure workflow exists
    workflow_result = ensure_workflow_exists(owner, repo)
    if not workflow_result["success"]:
        return {"success": False, "error": f"Could not create workflow: {workflow_result['error']}"}

    # Step 2: Add secrets automatically
    try:
        add_repo_secrets(owner, repo)
    except Exception as e:
        print(f"Could not add secrets: {e}")
        # Continue anyway - secrets might already exist

    # Step 3: Trigger the workflow
    dispatch_url = f"https://api.github.com/repos/{owner}/{repo}/dispatches"
    response = requests.post(
        dispatch_url,
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