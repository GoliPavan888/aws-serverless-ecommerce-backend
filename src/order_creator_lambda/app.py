import json
import uuid
from datetime import datetime, timezone

from shared.aws_clients import sqs_client
from shared.config import ORDER_PROCESSING_QUEUE_NAME
from shared.db import get_connection
from shared.logging_utils import get_logger

logger = get_logger("order_creator")


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _validate_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("user_id"), str) or not payload["user_id"].strip():
        errors.append("user_id must be a non-empty string")
    if not isinstance(payload.get("product_id"), str) or not payload["product_id"].strip():
        errors.append("product_id must be a non-empty string")
    quantity = payload.get("quantity")
    if not isinstance(quantity, int) or quantity <= 0:
        errors.append("quantity must be an integer greater than 0")
    return errors


def _insert_order(order_id: str, payload: dict) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (id, user_id, product_id, quantity, status)
                VALUES (%s, %s, %s, %s, 'PENDING')
                """,
                (order_id, payload["user_id"], payload["product_id"], payload["quantity"]),
            )


def _enqueue_order(order_id: str) -> str:
    sqs = sqs_client()
    queue_url = sqs.get_queue_url(QueueName=ORDER_PROCESSING_QUEUE_NAME)["QueueUrl"]
    resp = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"order_id": order_id, "created_at": datetime.now(timezone.utc).isoformat()}),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": "ORDER_PLACED"},
        },
    )
    return resp["MessageId"]


def lambda_handler(event, _context):
    logger.info("received order create request", extra={"extra": {"request_id": event.get("requestContext", {}).get("requestId")}})

    try:
        payload = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON body"})

    errors = _validate_payload(payload)
    if errors:
        return _response(400, {"error": "Validation failed", "details": errors})

    order_id = str(uuid.uuid4())

    try:
        _insert_order(order_id, payload)
        message_id = _enqueue_order(order_id)
    except Exception as exc:
        logger.exception("failed to create order", extra={"extra": {"order_id": order_id, "error": str(exc)}})
        return _response(500, {"error": "Failed to create order"})

    logger.info("order created and queued", extra={"extra": {"order_id": order_id, "message_id": message_id}})
    return _response(202, {"order_id": order_id, "status": "PENDING"})
