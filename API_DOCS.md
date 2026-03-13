# API Documentation

## POST /orders

Create an order asynchronously.

### Request

- Method: `POST`
- URL (LocalStack): `http://localhost:4566/restapis/{rest_api_id}/prod/_user_request_/orders`
- Headers: `Content-Type: application/json`
- Body:

```json
{
  "user_id": "user-123",
  "product_id": "product-456",
  "quantity": 2
}
```

### Success Response

- Status: `202 Accepted`
- Body:

```json
{
  "order_id": "d6f2e5f8-46b2-4ad8-9c3f-b8890facc123",
  "status": "PENDING"
}
```

### Validation Error

- Status: `400 Bad Request`
- Body:

```json
{
  "error": "Validation failed",
  "details": [
    "user_id must be a non-empty string",
    "quantity must be an integer greater than 0"
  ]
}
```

### Internal Error

- Status: `500 Internal Server Error`
- Body:

```json
{
  "error": "Failed to create order"
}
```
