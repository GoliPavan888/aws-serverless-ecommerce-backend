import json

from shared.logging_utils import get_logger

logger = get_logger("notification_service")


def lambda_handler(event, _context):
    for record in event.get("Records", []):
        sns = record.get("Sns", {})
        message = sns.get("Message", "{}")
        payload = json.loads(message)
        logger.info(
            "order status notification received",
            extra={
                "extra": {
                    "order_id": payload.get("order_id"),
                    "new_status": payload.get("new_status"),
                }
            },
        )
    return {"ok": True}
