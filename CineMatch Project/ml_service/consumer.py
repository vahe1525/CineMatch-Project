"""
CineMatch ML Service — Kafka Consumer + Recommendation Engine
=============================================================
Run from the project root:

    python ml_service/consumer.py

On startup:
  1. Builds recommendations for every existing user (SVD or top-rated fallback).
  2. Starts the Kafka consumer loop.

On user.rated / user.watched events:
  3. Rebuilds recommendations for that specific user.

On user.searched / user.clicked:
  4. Just logs the event (too frequent to trigger a rebuild).
"""
import json
import logging
import os
import sys
import time

# Make the project root importable so `from ml_service.x import y` works
# when this file is executed as `python ml_service/consumer.py`
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('cinematch.consumer')

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOOTSTRAP_SERVERS = os.environ.get('KAFKA_SERVERS', 'localhost:9092')
TOPICS            = ['user.rated', 'user.watched', 'user.searched', 'user.clicked']
CONSUMER_GROUP    = 'cinematch-ml'
RETRY_INTERVAL    = 5  # seconds between reconnect attempts

# ---------------------------------------------------------------------------
# DB helper (for enriching log lines only — recommender uses db_utils.py)
# ---------------------------------------------------------------------------
from ml_service.db_utils import get_movie_title   # noqa: E402


# ---------------------------------------------------------------------------
# Event processor
# ---------------------------------------------------------------------------
def process_message(topic: str, payload: dict) -> None:
    """Route an incoming Kafka event to the right handler."""

    user_id  = payload.get('user_id')
    movie_id = payload.get('movie_id')

    # Enriched log line
    parts = [f'user_id={user_id}']
    if movie_id:
        parts.append(f'"{get_movie_title(movie_id)}"')
    if 'score' in payload:
        parts.append(f'score={payload["score"]}')
    if 'action' in payload:
        parts.append(f'action={payload["action"]}')
    if 'query' in payload:
        parts.append(f'query="{payload["query"]}"')

    logger.info('[%-20s]  %s', topic, '  '.join(parts))

    if topic in ('user.rated', 'user.watched'):
        if user_id is None:
            logger.warning('No user_id in payload — skipping recommendation rebuild')
            return
        try:
            from ml_service.recommender import build_recommendations
            build_recommendations(user_id)
            logger.info('Updated recommendations for user %s', user_id)
        except Exception as exc:
            logger.warning('Recommendation rebuild failed for user %s: %s', user_id, exc)

    # user.searched and user.clicked: log only, no rebuild (too frequent)


# ---------------------------------------------------------------------------
# Consumer loop
# ---------------------------------------------------------------------------
def run():
    logger.info('CineMatch ML Consumer starting up')
    logger.info('Broker  : %s', BOOTSTRAP_SERVERS)
    logger.info('Topics  : %s', ', '.join(TOPICS))
    logger.info('Group   : %s', CONSUMER_GROUP)
    print()

    # --- Initial full recommendation build ---
    try:
        from ml_service.recommender import build_all_recommendations
        build_all_recommendations()
    except Exception as exc:
        logger.warning('Initial recommendation build failed: %s', exc)
    print()

    # --- Kafka consumer loop ---
    while True:
        try:
            from kafka import KafkaConsumer

            logger.info('Connecting to Kafka...')
            consumer = KafkaConsumer(
                *TOPICS,
                bootstrap_servers=BOOTSTRAP_SERVERS,
                group_id=CONSUMER_GROUP,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                value_deserializer=lambda b: json.loads(b.decode('utf-8')),
                consumer_timeout_ms=1000,   # non-blocking poll so Ctrl-C is responsive
                session_timeout_ms=10_000,
                heartbeat_interval_ms=3_000,
                request_timeout_ms=30_000,  # must be > session_timeout_ms
            )

            logger.info('Connected. Waiting for events... (Ctrl-C to stop)\n')

            while True:
                for message in consumer:
                    process_message(message.topic, message.value)

        except KeyboardInterrupt:
            logger.info('Stopped by user.')
            sys.exit(0)

        except Exception as exc:
            logger.warning('Kafka error: %s', exc)
            logger.info('Retrying in %d seconds...\n', RETRY_INTERVAL)
            time.sleep(RETRY_INTERVAL)


if __name__ == '__main__':
    run()
