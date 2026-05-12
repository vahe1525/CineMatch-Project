from app import db
from app.models import EventLog


def log_event(user_id, event_type, payload):
    """
    Persist a user action to EventLog.
    Phase 4 will extend this function to also produce the event to Kafka —
    all Kafka logic will live here so no routes need to change.
    """
    event = EventLog(user_id=user_id, event_type=event_type, payload=payload)
    db.session.add(event)
    db.session.commit()
