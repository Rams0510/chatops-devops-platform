import requests
import os
import base64
import time
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("GITHUB_TOKEN")
owner = "Rams0510"
repo  = "note_making"

HEADERS = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json"
}

print("=" * 50)
print("STEP 1: Check token")
print("=" * 50)
r = requests.get("https://api.github.com/user", headers=HEADERS)
print(f"Token valid: {r.status_code == 200}")

print("\n" + "=" * 50)
print("STEP 2: Check repo access")
print("=" * 50)
r2 = requests.get(
    f"https://api.github.com/repos/{owner}/{repo}",
    headers=HEADERS
)
print(f"Repo access status: {r2.status_code}")
if r2.status_code == 200:
    print(f"Repo found: {r2.json()['full_name']}")
else:
    print(f"Error: {r2.text}")

print("\n" + "=" * 50)
print("STEP 3: Check if workflow exists")
print("=" * 50)
file_path = ".github/workflows/chatops-deploy.yml"
r3 = requests.get(
    f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
    headers=HEADERS
)
print(f"Workflow exists: {r3.status_code == 200}")
print(f"Status code: {r3.status_code}")

print("\n" + "=" * 50)
print("STEP 4: Create workflow if missing")
print("=" * 50)
if r3.status_code != 200:
    WORKFLOW = """name: ChatOps Deployment
on:
  repository_dispatch:
    types: [chatops-deploy]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Deploy
        run: |
          echo "Deploying to ${{ github.event.client_payload.environment }}"
          echo "ID: ${{ github.event.client_payload.deployment_id }}"
          echo "Success!"
"""
    content_encoded = base64.b64encode(WORKFLOW.encode()).decode()
    r4 = requests.put(
        f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
        headers=HEADERS,
        json={
            "message": "chore: add chatops workflow",
            "content": content_encoded
        }
    )
    print(f"Create workflow status: {r4.status_code}")
    print(f"Response: {r4.text[:300]}")
    if r4.status_code == 201:
        print("Workflow created! Waiting 5 seconds...")
        time.sleep(5)
    else:
        print("FAILED to create workflow - stopping here")
        exit()
else:
    print("Workflow already exists - skipping creation")

print("\n" + "=" * 50)
print("STEP 5: Trigger dispatch")
print("=" * 50)
r5 = requests.post(
    f"https://api.github.com/repos/{owner}/{repo}/dispatches",
    headers=HEADERS,
    json={
        "event_type": "chatops-deploy",
        "client_payload": {
            "environment": "dev",
            "deployment_id": "999"
        }
    }
)
print(f"Dispatch status: {r5.status_code}")
print(f"Response: '{r5.text}'")

print("\n" + "=" * 50)
print("STEP 6: Check if workflow ran")
print("=" * 50)
time.sleep(5)
r6 = requests.get(
    f"https://api.github.com/repos/{owner}/{repo}/actions/runs",
    headers=HEADERS
)
print(f"Actions runs status: {r6.status_code}")
runs = r6.json().get("workflow_runs", [])
print(f"Total runs found: {len(runs)}")
if runs:
    latest = runs[0]
    print(f"Latest run: {latest['name']}")
    print(f"Status: {latest['status']}")
    print(f"Conclusion: {latest['conclusion']}")
    print(f"URL: {latest['html_url']}")
else:
    print("NO RUNS FOUND!")