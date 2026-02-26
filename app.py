from flask import Flask, request, jsonify
from database import Base, engine
from slack_routes import slack_bp
from models import Deployment
from database import SessionLocal
from chatops_services.slack_service import notify_slack
from chatops_services.security import verify_webhook_secret
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
Base.metadata.create_all(bind=engine)

# Register Slack routes
app.register_blueprint(slack_bp)

# ── Root ─────────────────────────────────────────────────────
@app.route("/")
def index():
    return jsonify({"message": "ChatOps Platform Running"})

# ── Health Check ─────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "running"})

# ── GitHub Webhook Receiver ───────────────────────────────────
@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    if not verify_webhook_secret(request):
        return jsonify({"error": "Unauthorized"}), 401

    data          = request.get_json()
    deployment_id = int(data.get("deployment_id"))
    status        = data.get("status")
    environment   = data.get("environment")
    run_url       = data.get("run_url", "")

    db = SessionLocal()
    deployment = db.query(Deployment).get(deployment_id)

    if deployment:
        deployment.status  = status
        deployment.run_url = run_url
        db.commit()
        db.refresh(deployment)
        notify_slack(deployment, status, environment, run_url)

    db.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)