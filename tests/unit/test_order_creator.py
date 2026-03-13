import json

from order_creator_lambda.app import _validate_payload, lambda_handler


def test_validate_payload_success():
    payload = {"user_id": "u1", "product_id": "p1", "quantity": 2}
    assert _validate_payload(payload) == []


def test_validate_payload_errors():
    payload = {"user_id": "", "product_id": 1, "quantity": 0}
    errors = _validate_payload(payload)
    assert len(errors) == 3


def test_lambda_handler_bad_json():
    response = lambda_handler({"body": "{"}, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error"] == "Invalid JSON body"
