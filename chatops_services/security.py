import hmac
import hashlib
import time
import os

def verify_slack_request(request) -> bool:
    """Verifies that a request genuinely came from Slack."""
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    timestamp  = request.headers.get("X-Slack-Request-Timestamp", "")
    signature  = request.headers.get("X-Slack-Signature", "")

    # Block replay attacks older than 5 minutes
    if abs(time.time() - int(timestamp)) > 300:
        return False

    base = f"v0:{timestamp}:{request.get_data(as_text=True)}"
    expected = "v0=" + hmac.new(
        signing_secret.encode(),
        base.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_webhook_secret(request) -> bool:
    """Verifies that a webhook came from your GitHub Action."""
    secret   = os.environ.get("CHATOPS_WEBHOOK_SECRET", "")
    incoming = request.headers.get("X-Webhook-Secret", "")
    return hmac.compare_digest(secret, incoming)