import requests
import os

def notify_slack(deployment, status: str, environment: str, run_url: str):
    token   = os.environ.get("SLACK_BOT_TOKEN")
    channel = os.environ.get("SLACK_DEPLOY_CHANNEL", "#deployments")

    icon  = "✅" if status == "SUCCESS" else "❌"
    color = "#36a64f" if status == "SUCCESS" else "#ff0000"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{icon} *Deployment {status}*\n"
                    f"*Repo:* {deployment.repo_url}\n"
                    f"*Environment:* `{environment}`\n"
                    f"*Triggered by:* @{deployment.user_name}\n"
                    f"*Deployment ID:* `{deployment.id}`"
                )
            }
        }
    ]

    # Show live URL if SUCCESS
    if status == "SUCCESS" and deployment.url:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🌐 *Live URL:* <{deployment.url}|{deployment.url}>"
            }
        })
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🌐 Open Live App"},
                    "url": deployment.url,
                    "style": "primary"
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔗 View GitHub Run"},
                    "url": run_url
                }
            ]
        })
    else:
        if run_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🔗 View GitHub Run"},
                        "url": run_url
                    }
                ]
            })

    payload = {
        "channel": channel,
        "attachments": [{"color": color, "blocks": blocks}]
    }

    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    print(f"Slack notify: {response.status_code}, {response.text}")