# pyright: reportMissingImports=false
import json
import os
import time

import boto3
import psycopg
import requests

AWS_REGION = "us-east-1"
AWS_ENDPOINT_URL = "http://localstack:4566"
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "test")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
DB_DSN = "host=postgres port=5432 dbname=orders_db user=orders_user password=orders_password"


def _aws_client(service_name: str):
    return boto3.client(
        service_name,
        region_name=AWS_REGION,
        endpoint_url=AWS_ENDPOINT_URL,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )


def _get_rest_api_id() -> str:
    apigw = _aws_client("apigateway")
    apis = apigw.get_rest_apis().get("items", [])
    for api in apis:
        if api.get("name") == "order-api":
            return api["id"]
    raise AssertionError("order-api not found")


def _fetch_status(order_id: str) -> str | None:
    with psycopg.connect(DB_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
            row = cur.fetchone()
            return row[0] if row else None


def _notification_logged(order_id: str) -> bool:
    logs = _aws_client("logs")
    groups = logs.describe_log_groups(logGroupNamePrefix="/aws/lambda/NotificationService").get("logGroups", [])
    if not groups:
        return False

    streams = logs.describe_log_streams(logGroupName=groups[0]["logGroupName"], orderBy="LastEventTime", descending=True).get("logStreams", [])
    for stream in streams[:3]:
        events = logs.get_log_events(
            logGroupName=groups[0]["logGroupName"],
            logStreamName=stream["logStreamName"],
            limit=50,
        ).get("events", [])
        for event in events:
            if order_id in event.get("message", ""):
                return True
    return False


def test_order_async_flow_end_to_end():
    rest_api_id = _get_rest_api_id()
    url = f"http://localstack:4566/restapis/{rest_api_id}/prod/_user_request_/orders"

    payload = {"user_id": "integration-user", "product_id": "product-1", "quantity": 1}
    response = requests.post(url, json=payload, timeout=10)

    assert response.status_code == 202
    body = response.json()
    assert "order_id" in body
    order_id = body["order_id"]

    terminal_status = None
    for _ in range(30):
        terminal_status = _fetch_status(order_id)
        if terminal_status in {"CONFIRMED", "FAILED"}:
            break
        time.sleep(1)

    assert terminal_status in {"CONFIRMED", "FAILED"}

    logged = False
    for _ in range(20):
        logged = _notification_logged(order_id)
        if logged:
            break
        time.sleep(1)

    assert logged
