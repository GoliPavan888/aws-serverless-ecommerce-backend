import os


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


AWS_REGION = get_env("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = get_env("AWS_ENDPOINT_URL", "http://localhost:4566")

DB_HOST = get_env("DB_HOST", "localhost")
DB_PORT = int(get_env("DB_PORT", "5432"))
DB_NAME = get_env("DB_NAME", "orders_db")
DB_USER = get_env("DB_USER", "orders_user")
DB_PASSWORD = get_env("DB_PASSWORD", "orders_password")

ORDER_PROCESSING_QUEUE_NAME = get_env("ORDER_PROCESSING_QUEUE_NAME", "OrderProcessingQueue")
ORDER_STATUS_TOPIC_NAME = get_env("ORDER_STATUS_TOPIC_NAME", "OrderStatusNotifications")

LOG_LEVEL = get_env("LOG_LEVEL", "INFO")
PROCESSING_FAILURE_RATE = float(get_env("PROCESSING_FAILURE_RATE", "0.2"))
IDEMPOTENCY_WINDOW_SECONDS = int(get_env("IDEMPOTENCY_WINDOW_SECONDS", "900"))
