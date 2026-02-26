from flask import Flask, request, jsonify
from database import Base, engine
from slack_routes import slack_bp
from models import Deployment
from database import SessionLocal
from chatops_services.slack_service import notify_slack
from chatops_services.security import verify_webhook_secret
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
Base.metadata.create_all(bind=engine)

# Register Slack routes
app.register_blueprint(slack_bp)

# ── GitHub Webhook Receiver ───────────────────────────────────
@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    if not verify_webhook_secret(request):
        return jsonify({"error": "Unauthorized"}), 401

    data          = request.get_json()
    deployment_id = int(data.get("deployment_id"))
    status        = data.get("status")        # "SUCCESS" or "FAILED"
    environment   = data.get("environment")
    run_url       = data.get("run_url", "")

    # Update DB
    db = SessionLocal()
    deployment = db.query(Deployment).get(deployment_id)

    if deployment:
        deployment.status  = status
        deployment.run_url = run_url
        db.commit()
        db.refresh(deployment)
        # Notify Slack
        notify_slack(deployment, status, environment, run_url)

    db.close()
    return jsonify({"ok": True})


# ── Health Check ─────────────────────────────────────────────
@app.route("/")
def index():
    return "OK"  # this is what you're seeing

@app.route("/health")
def health():
    return jsonify({"status": "running"})  # ADD THIS

if __name__ == "__main__":
    app.run(debug=True)