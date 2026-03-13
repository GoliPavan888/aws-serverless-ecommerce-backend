from order_processor_lambda import app


def test_processor_idempotent_skip(monkeypatch):
    events = {"Records": [{"messageId": "m1", "body": '{"order_id": "o1"}'}]}

    def fake_update(_order_id, _status):
        return True, "CONFIRMED"

    publish_calls = []

    def fake_publish(order_id, status):
        publish_calls.append((order_id, status))

    monkeypatch.setattr(app, "_update_order_status", fake_update)
    monkeypatch.setattr(app, "_publish_status", fake_publish)

    response = app.lambda_handler(events, None)
    assert response == {"batchItemFailures": []}
    assert publish_calls == []


def test_processor_publish(monkeypatch):
    events = {"Records": [{"messageId": "m1", "body": '{"order_id": "o1"}'}]}

    monkeypatch.setattr(app, "PROCESSING_FAILURE_RATE", 0.0)
    monkeypatch.setattr(app.random, "random", lambda: 0.9)
    monkeypatch.setattr(app, "_update_order_status", lambda _order_id, _status: (False, "CONFIRMED"))

    publish_calls = []

    def fake_publish(order_id, status):
        publish_calls.append((order_id, status))

    monkeypatch.setattr(app, "_publish_status", fake_publish)

    app.lambda_handler(events, None)
    assert publish_calls == [("o1", "CONFIRMED")]
