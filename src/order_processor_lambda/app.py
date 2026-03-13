import json
import random
from datetime import datetime, timezone

from shared.aws_clients import sns_client
from shared.config import ORDER_STATUS_TOPIC_NAME, PROCESSING_FAILURE_RATE
from shared.db import get_connection
from shared.logging_utils import get_logger

logger = get_logger("order_processor")


TERMINAL_STATES = {"CONFIRMED", "FAILED"}


def _get_topic_arn() -> str:
    sns = sns_client()
    topics = sns.list_topics().get("Topics", [])
    expected_suffix = f":{ORDER_STATUS_TOPIC_NAME}"
    for topic in topics:
        arn = topic["TopicArn"]
        if arn.endswith(expected_suffix):
            return arn
    raise RuntimeError(f"SNS topic not found: {ORDER_STATUS_TOPIC_NAME}")


def _update_order_status(order_id: str, new_status: str) -> tuple[bool, str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError(f"Order not found: {order_id}")

            current_status = row["status"]
            if current_status in TERMINAL_STATES:
                return True, current_status

            cur.execute(
                """
                UPDATE orders
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (new_status, order_id),
            )
            return False, new_status


def _publish_status(order_id: str, status: str) -> None:
    payload = {
        "order_id": order_id,
        "new_status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    sns = sns_client()
    topic_arn = _get_topic_arn()
    sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(payload),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": "ORDER_STATUS_UPDATED"},
            "status": {"DataType": "String", "StringValue": status},
        },
    )


def lambda_handler(event, _context):
    records = event.get("Records", [])
    logger.info("processing sqs batch", extra={"extra": {"record_count": len(records)}})

    for record in records:
        message_id = record.get("messageId")
        body = json.loads(record.get("body") or "{}")
        order_id = body.get("order_id")
        if not order_id:
            logger.error("missing order_id in message", extra={"extra": {"message_id": message_id}})
            continue

        try:
            status = "FAILED" if random.random() < PROCESSING_FAILURE_RATE else "CONFIRMED"
            duplicate, final_status = _update_order_status(order_id, status)
            if duplicate:
                logger.info("idempotent skip", extra={"extra": {"order_id": order_id, "status": final_status}})
                continue
            _publish_status(order_id, final_status)
            logger.info("order processed", extra={"extra": {"order_id": order_id, "status": final_status}})
        except Exception as exc:
            logger.exception(
                "failed processing order",
                extra={"extra": {"order_id": order_id, "message_id": message_id, "error": str(exc)}},
            )
            raise

    return {"batchItemFailures": []}
