import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 'sqlite:///cinematch.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Kafka — Phase 4-ին կօգտագործվի
    KAFKA_BOOTSTRAP_SERVERS = os.environ.get('KAFKA_SERVERS', 'localhost:9092')