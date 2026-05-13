"""
Kafka producer — lazy-initialized, fail-safe.

The Flask app works normally when Kafka is not running.
All errors are caught and logged as warnings.
"""
import json
import logging
import time

logger = logging.getLogger(__name__)

_producer = None          # None = not yet tried / last attempt failed
_next_retry_at = 0.0     # epoch timestamp; 0 = retry immediately
_RETRY_INTERVAL = 30     # seconds to wait after a failed connection attempt


def _get_producer():
    """
    Return the cached KafkaProducer, or None if Kafka is unavailable.
    Retries connection after _RETRY_INTERVAL seconds following a failure.
    """
    global _producer, _next_retry_at

    if _producer is not None:
        return _producer

    if time.time() < _next_retry_at:
        return None  # still in cooldown — don't hammer a down broker

    bootstrap = 'localhost:9092'
    try:
        # current_app is available when called from a Flask request context
        from flask import current_app
        bootstrap = current_app.config.get('KAFKA_BOOTSTRAP_SERVERS', bootstrap)
    except RuntimeError:
        pass  # called outside Flask app context (e.g. tests)

    try:
        from kafka import KafkaProducer
        _producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=3000,
            max_block_ms=3000,
            reconnect_backoff_ms=500,
            reconnect_backoff_max_ms=3000,
        )
        logger.info('Kafka producer connected to %s', bootstrap)
    except Exception as exc:
        logger.warning('Kafka unavailable (%s) — events will not be streamed', exc)
        _next_retry_at = time.time() + _RETRY_INTERVAL
        _producer = None

    return _producer


def produce_event(topic: str, payload_dict: dict) -> None:
    """
    Serialize payload_dict to JSON and send it to the given Kafka topic.

    Silently swallows all errors so the Flask app keeps working without Kafka.
    If send/flush fails (Kafka went down mid-run) the producer is reset so the
    next call will attempt a fresh connection after the retry cooldown.
    """
    global _producer
    try:
        producer = _get_producer()
        if producer is None:
            return
        producer.send(topic, value=payload_dict)
        producer.flush(timeout=1)
    except Exception as exc:
        logger.warning('Kafka produce failed [topic=%s]: %s — will retry later', topic, exc)
        _producer = None  # force reconnect on next call
