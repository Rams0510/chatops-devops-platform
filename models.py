from database import Base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class Deployment(Base):
    __tablename__ = "deployments"

    id          = Column(Integer, primary_key=True, index=True)
    repo_url    = Column(String, nullable=False)
    user_name   = Column(String, nullable=False)
    environment = Column(String, default="dev")        # NEW: dev/staging/prod
    status      = Column(String, default="DEPLOYING")  # DEPLOYING/SUCCESS/FAILED
    run_url     = Column(String, nullable=True)        # NEW: GitHub Actions run link
    timestamp   = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "repo_url": self.repo_url,
            "user_name": self.user_name,
            "environment": self.environment,
            "status": self.status,
            "run_url": self.run_url,
            "timestamp": str(self.timestamp)
        }