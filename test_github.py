import requests
import os
from dotenv import load_dotenv

load_dotenv()

token = os.environ.get("GITHUB_TOKEN")

print(f"Token value: '{token}'")
print(f"Token length: {len(token) if token else 0}")
print(f"Starts with ghp_: {token.startswith('ghp_') if token else False}")
print("---")

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json"
}

# Test 1: Token valid
print("=" * 50)
print("TEST 1: Token Valid")
print("=" * 50)
r1 = requests.get("https://api.github.com/user", headers=headers)
print(f"Status: {r1.status_code}")
print(f"GitHub User: {r1.json().get('login', 'ERROR')}")

# Test 2: Access YOUR repo
print("\n" + "=" * 50)
print("TEST 2: Your Repo Access (Rams0510/note_making)")
print("=" * 50)
r2 = requests.get(
    "https://api.github.com/repos/Rams0510/note_making",
    headers=headers
)
print(f"Status: {r2.status_code}")
print(f"Result: {'ACCESS OK' if r2.status_code == 200 else 'NO ACCESS - ' + r2.json().get('message', '')}")

# Test 3: Access OTHER person's repo
print("\n" + "=" * 50)
print("TEST 3: Other Repo Access (pujalameghana/YOUTUBE-CLONE)")
print("=" * 50)
r3 = requests.get(
    "https://api.github.com/repos/pujalameghana/YOUTUBE-CLONE",
    headers=headers
)
print(f"Status: {r3.status_code}")
if r3.status_code == 200:
    print("Result: ACCESS OK - you can deploy this repo!")
elif r3.status_code == 404:
    print("Result: REPO NOT FOUND - either private or doesn't exist")
    print("Fix: pujalameghana must add Rams0510 as collaborator")
elif r3.status_code == 403:
    print("Result: NO PERMISSION - you don't have access")
    print("Fix: pujalameghana must add Rams0510 as collaborator")
else:
    print(f"Result: {r3.json().get('message', 'Unknown error')}")

# Test 4: Trigger dispatch on YOUR repo
print("\n" + "=" * 50)
print("TEST 4: Trigger Dispatch (Rams0510/note_making)")
print("=" * 50)
r4 = requests.post(
    "https://api.github.com/repos/Rams0510/note_making/dispatches",
    headers=headers,
    json={
        "event_type": "chatops-deploy",
        "client_payload": {
            "environment": "dev",
            "deployment_id": "999"
        }
    }
)
print(f"Status: {r4.status_code}")
if r4.status_code == 204:
    print("Result: SUCCESS - workflow triggered!")
    print("Check: github.com/Rams0510/note_making -> Actions tab")
else:
    print(f"Result: FAILED - {r4.text}")

# Test 5: Trigger dispatch on OTHER repo
print("\n" + "=" * 50)
print("TEST 5: Trigger Dispatch (pujalameghana/YOUTUBE-CLONE)")
print("=" * 50)
r5 = requests.post(
    "https://api.github.com/repos/pujalameghana/YOUTUBE-CLONE/dispatches",
    headers=headers,
    json={
        "event_type": "chatops-deploy",
        "client_payload": {
            "environment": "dev",
            "deployment_id": "999"
        }
    }
)
print(f"Status: {r5.status_code}")
if r5.status_code == 204:
    print("Result: SUCCESS - workflow triggered!")
elif r5.status_code == 404:
    print("Result: FAILED - No access to this repo")
    print("Fix: pujalameghana must:")
    print("  1. Go to their repo -> Settings -> Collaborators")
    print("  2. Add 'Rams0510' as collaborator")
    print("  3. You accept the invitation")
    print("  4. Then /deploy will work for their repo!")
else:
    print(f"Result: FAILED - {r5.text}")

print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)
print(f"Your repos:        {'WORKS' if r4.status_code == 204 else 'BROKEN'}")
print(f"pujalameghana repo: {'WORKS' if r5.status_code == 204 else 'NEEDS COLLABORATOR ACCESS'}")