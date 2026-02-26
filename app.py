from flask import Flask, request, jsonify, render_template
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

# ── Dashboard ─────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ── API — All Deployments for Dashboard ──────────────────────
@app.route("/api/deployments")
def api_deployments():
    db = SessionLocal()
    try:
        deployments = db.query(Deployment)\
            .order_by(Deployment.id.desc())\
            .limit(50)\
            .all()
        return jsonify({
            "deployments": [d.to_dict() for d in deployments]
        })
    finally:
        db.close()

# ── API — Single Deployment Status ───────────────────────────
@app.route("/api/deployments/<int:deployment_id>")
def api_deployment_status(deployment_id):
    db = SessionLocal()
    try:
        deployment = db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()
        if not deployment:
            return jsonify({"error": "Deployment not found"}), 404
        return jsonify(deployment.to_dict())
    finally:
        db.close()

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
    try:
        deployment = db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()

        if deployment:
            deployment.status  = status
            deployment.run_url = run_url
            db.commit()
            db.refresh(deployment)
            notify_slack(deployment, status, environment, run_url)
    finally:
        db.close()

    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)