from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    store_id: str
    user_id: str
    action: str
    resource: str
    outcome: str
    timestamp: datetime
