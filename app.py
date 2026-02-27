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

# Force create all tables in PostgreSQL
print("Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
except Exception as e:
    print(f"Error creating tables: {e}")

# Register Slack routes
app.register_blueprint(slack_bp)

@app.route("/")
def index():
    return jsonify({"message": "ChatOps Platform Running"})

@app.route("/health")
def health():
    return jsonify({"status": "running"})

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/deployments")
def api_deployments():
    db = SessionLocal()
    try:
        deployments = db.query(Deployment)\
            .order_by(Deployment.id.desc())\
            .limit(50)\
            .all()
        print(f"Found {len(deployments)} deployments")
        return jsonify({
            "deployments": [d.to_dict() for d in deployments]
        })
    except Exception as e:
        print(f"Error fetching deployments: {e}")
        return jsonify({"deployments": [], "error": str(e)})
    finally:
        db.close()

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

@app.route("/webhook/github", methods=["POST"])
def github_webhook():
    if not verify_webhook_secret(request):
        print("Webhook secret FAILED")
        return jsonify({"error": "Unauthorized"}), 401

    data          = request.get_json()
    print(f"Webhook received: {data}")
    deployment_id = int(data.get("deployment_id"))
    status        = data.get("status")
    environment   = data.get("environment")
    run_url       = data.get("run_url", "")

    db = SessionLocal()
    try:
        deployment = db.query(Deployment).filter(
            Deployment.id == deployment_id
        ).first()
        print(f"Found deployment: {deployment}")
        if deployment:
            deployment.status  = status
            deployment.run_url = run_url
            db.commit()
            db.refresh(deployment)
            print(f"Updated to {status}")
            notify_slack(deployment, status, environment, run_url)
    except Exception as e:
        print(f"Webhook error: {e}")
        db.rollback()
    finally:
        db.close()

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True)