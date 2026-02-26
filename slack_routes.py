from flask import Blueprint, request, jsonify
from database import SessionLocal
from models import Deployment
from chatops_services.github_service import trigger_github_deployment
from datetime import datetime

slack_bp = Blueprint("slack", __name__)

VALID_ENVIRONMENTS = ["dev", "staging", "prod"]

@slack_bp.route("/slack", methods=["POST"])
def slack_commands():
    command   = request.form.get("command")
    text      = request.form.get("text", "").strip()
    user_name = request.form.get("user_name", "unknown")

    # ── /deploy ──────────────────────────────────────────────
    if command == "/deploy":
        parts = text.split()

        if len(parts) < 2:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Usage: `/deploy <github-repo-url> <environment>`\nEnvironments: `dev`, `staging`, `prod`"
            })

        repo_url    = parts[0]
        environment = parts[1].lower()

        if environment not in VALID_ENVIRONMENTS:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Invalid environment `{environment}`. Choose from: `dev`, `staging`, `prod`"
            })

        # Save to DB
        db = SessionLocal()
        try:
            deployment = Deployment(
                repo_url=repo_url,
                user_name=user_name,
                environment=environment,
                status="DEPLOYING",
                timestamp=datetime.utcnow()
            )
            db.add(deployment)
            db.commit()
            db.refresh(deployment)
            deployment_id = deployment.id
        finally:
            db.close()

        # Trigger GitHub Actions
        result = trigger_github_deployment(repo_url, environment, deployment_id)

        if not result["success"]:
            db = SessionLocal()
            try:
                dep = db.query(Deployment).filter(Deployment.id == deployment_id).first()
                if dep:
                    dep.status = "TRIGGER_FAILED"
                    db.commit()
            finally:
                db.close()
            return jsonify({
                "response_type": "ephemeral",
                "text": f"GitHub trigger failed: {result['error']}"
            })

        return jsonify({
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Deployment Triggered!"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Repo:*\n{repo_url}"},
                        {"type": "mrkdwn", "text": f"*Environment:*\n`{environment}`"},
                        {"type": "mrkdwn", "text": f"*Triggered by:*\n@{user_name}"},
                        {"type": "mrkdwn", "text": f"*Deployment ID:*\n`{deployment_id}`"}
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Status: `DEPLOYING` - I'll post here when it finishes."
                    }
                }
            ]
        })

    # ── /deploy-status ────────────────────────────────────────
    elif command == "/deploy-status":
        db = SessionLocal()
        try:
            deployments = db.query(Deployment)\
                .order_by(Deployment.id.desc())\
                .limit(5)\
                .all()

            if not deployments:
                return jsonify({
                    "response_type": "ephemeral",
                    "text": "No deployments found yet."
                })

            blocks = [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Recent Deployments"}
                }
            ]

            status_icons = {
                "SUCCESS":        "SUCCESS",
                "FAILED":         "FAILED",
                "DEPLOYING":      "DEPLOYING",
                "TRIGGER_FAILED": "TRIGGER_FAILED"
            }

            for dep in deployments:
                status_label = status_icons.get(dep.status, dep.status)
                blocks.append({
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Repo:*\n{dep.repo_url}"},
                        {"type": "mrkdwn", "text": f"*Env:*\n`{dep.environment}`"},
                        {"type": "mrkdwn", "text": f"*Status:*\n`{status_label}`"},
                        {"type": "mrkdwn", "text": f"*By:*\n@{dep.user_name}"}
                    ]
                })
                blocks.append({"type": "divider"})

            return jsonify({
                "response_type": "ephemeral",
                "blocks": blocks
            })

        except Exception as e:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error fetching status: {str(e)}"
            })
        finally:
            db.close()

    return jsonify({"text": "Unknown command."})