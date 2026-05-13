import logging

from app import db
from app.models import EventLog

logger = logging.getLogger(__name__)


def log_event(user_id, event_type, payload):
    """
    1. Persist the event to EventLog in the DB (always).
    2. Produce it to the matching Kafka topic (best-effort).

    The Kafka payload includes user_id so the ML consumer can trigger
    per-user recommendation rebuilds without a DB lookup.

    All Kafka errors are caught — the Flask app keeps working normally
    whether or not Kafka / docker-compose is running.
    """
    # --- DB write (always) ---
    event = EventLog(user_id=user_id, event_type=event_type, payload=payload)
    db.session.add(event)
    db.session.commit()

    # --- Kafka produce (best-effort, user_id added to payload) ---
    try:
        from app.kafka_producer import produce_event
        produce_event(event_type, {**payload, 'user_id': user_id})
    except Exception as exc:
        logger.warning('log_event: Kafka produce skipped: %s', exc)
