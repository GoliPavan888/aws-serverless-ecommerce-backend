#!/bin/bash
set -euo pipefail

export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-test}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-test}
export AWS_DEFAULT_REGION=${AWS_REGION:-us-east-1}

function lambda_arn() {
  awslocal lambda get-function --function-name "$1" --query 'Configuration.FunctionArn' --output text
}

function ensure_lambda() {
  local function_name=$1
  local zip_path=$2
  local environment=$3

  if awslocal lambda get-function --function-name "$function_name" >/dev/null 2>&1; then
    awslocal lambda update-function-code \
      --function-name "$function_name" \
      --zip-file "fileb://$zip_path" >/dev/null

    awslocal lambda update-function-configuration \
      --function-name "$function_name" \
      --runtime python3.11 \
      --handler app.lambda_handler \
      --timeout 20 \
      --environment "$environment" >/dev/null
    return
  fi

  awslocal lambda create-function \
    --function-name "$function_name" \
    --runtime python3.11 \
    --handler app.lambda_handler \
    --zip-file "fileb://$zip_path" \
    --role "arn:aws:iam::000000000000:role/lambda-role" \
    --timeout 20 \
    --environment "$environment" >/dev/null
}

function resource_id_by_path() {
  local rest_api_id=$1
  local path=$2
  awslocal apigateway get-resources --rest-api-id "$rest_api_id" --query "items[?path=='$path'].id | [0]" --output text
}

awslocal --version
python3 /etc/localstack/init/ready.d/package_lambdas.py

DLQ_URL=$(awslocal sqs create-queue --queue-name "${ORDER_PROCESSING_DLQ_NAME}" --query 'QueueUrl' --output text)
DLQ_ARN=$(awslocal sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

QUEUE_URL=$(awslocal sqs create-queue --queue-name "${ORDER_PROCESSING_QUEUE_NAME}" --query 'QueueUrl' --output text)
cat >/tmp/order-processing-queue-attributes.json <<EOF
{
  "RedrivePolicy": "{\"maxReceiveCount\":\"3\",\"deadLetterTargetArn\":\"${DLQ_ARN}\"}"
}
EOF
awslocal sqs set-queue-attributes --queue-url "$QUEUE_URL" --attributes file:///tmp/order-processing-queue-attributes.json >/dev/null
QUEUE_ARN=$(awslocal sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

TOPIC_ARN=$(awslocal sns create-topic --name "${ORDER_STATUS_TOPIC_NAME}" --query 'TopicArn' --output text)

ensure_lambda \
  "${ORDER_CREATOR_FUNCTION_NAME}" \
  "/workspace/dist/OrderCreator.zip" \
  "Variables={AWS_REGION=${AWS_REGION},AWS_ENDPOINT_URL=http://localstack:4566,DB_HOST=postgres,DB_PORT=5432,DB_NAME=${DB_NAME},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD},ORDER_PROCESSING_QUEUE_NAME=${ORDER_PROCESSING_QUEUE_NAME},LOG_LEVEL=${LOG_LEVEL}}"

ensure_lambda \
  "${ORDER_PROCESSOR_FUNCTION_NAME}" \
  "/workspace/dist/OrderProcessor.zip" \
  "Variables={AWS_REGION=${AWS_REGION},AWS_ENDPOINT_URL=http://localstack:4566,DB_HOST=postgres,DB_PORT=5432,DB_NAME=${DB_NAME},DB_USER=${DB_USER},DB_PASSWORD=${DB_PASSWORD},ORDER_STATUS_TOPIC_NAME=${ORDER_STATUS_TOPIC_NAME},PROCESSING_FAILURE_RATE=${PROCESSING_FAILURE_RATE},LOG_LEVEL=${LOG_LEVEL}}"

ensure_lambda \
  "${NOTIFICATION_SERVICE_FUNCTION_NAME}" \
  "/workspace/dist/NotificationService.zip" \
  "Variables={LOG_LEVEL=${LOG_LEVEL}}"

ORDER_PROCESSOR_ARN=$(lambda_arn "${ORDER_PROCESSOR_FUNCTION_NAME}")
NOTIFICATION_ARN=$(lambda_arn "${NOTIFICATION_SERVICE_FUNCTION_NAME}")
ORDER_CREATOR_ARN=$(lambda_arn "${ORDER_CREATOR_FUNCTION_NAME}")

awslocal lambda create-event-source-mapping \
  --function-name "${ORDER_PROCESSOR_FUNCTION_NAME}" \
  --batch-size 10 \
  --event-source-arn "$QUEUE_ARN" >/dev/null || true

awslocal lambda add-permission \
  --function-name "${NOTIFICATION_SERVICE_FUNCTION_NAME}" \
  --statement-id "sns-invoke" \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn "$TOPIC_ARN" || true

awslocal sns subscribe \
  --topic-arn "$TOPIC_ARN" \
  --protocol lambda \
  --notification-endpoint "$NOTIFICATION_ARN" >/dev/null

REST_API_ID=$(awslocal apigateway get-rest-apis --query "items[?name=='order-api'].id | [0]" --output text)
if [ "$REST_API_ID" = "None" ] || [ -z "$REST_API_ID" ]; then
  REST_API_ID=$(awslocal apigateway create-rest-api --name order-api --query 'id' --output text)
fi

ROOT_RESOURCE_ID=$(awslocal apigateway get-resources --rest-api-id "$REST_API_ID" --query 'items[0].id' --output text)
ORDERS_RESOURCE_ID=$(resource_id_by_path "$REST_API_ID" "/orders")
if [ "$ORDERS_RESOURCE_ID" = "None" ] || [ -z "$ORDERS_RESOURCE_ID" ]; then
  ORDERS_RESOURCE_ID=$(awslocal apigateway create-resource --rest-api-id "$REST_API_ID" --parent-id "$ROOT_RESOURCE_ID" --path-part orders --query 'id' --output text)
fi

awslocal apigateway put-method --rest-api-id "$REST_API_ID" --resource-id "$ORDERS_RESOURCE_ID" --http-method POST --authorization-type NONE >/dev/null || true
awslocal apigateway put-method-response --rest-api-id "$REST_API_ID" --resource-id "$ORDERS_RESOURCE_ID" --http-method POST --status-code 202
awslocal apigateway put-method-response --rest-api-id "$REST_API_ID" --resource-id "$ORDERS_RESOURCE_ID" --http-method POST --status-code 400
awslocal apigateway put-method-response --rest-api-id "$REST_API_ID" --resource-id "$ORDERS_RESOURCE_ID" --http-method POST --status-code 500

INTEGRATION_URI="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/${ORDER_CREATOR_ARN}/invocations"
awslocal apigateway put-integration \
  --rest-api-id "$REST_API_ID" \
  --resource-id "$ORDERS_RESOURCE_ID" \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "$INTEGRATION_URI" >/dev/null

awslocal lambda add-permission \
  --function-name "${ORDER_CREATOR_FUNCTION_NAME}" \
  --statement-id "apigw-invoke" \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${AWS_REGION}:000000000000:${REST_API_ID}/*/POST/orders" || true

awslocal apigateway create-deployment --rest-api-id "$REST_API_ID" --stage-name prod >/dev/null

echo "$REST_API_ID" > /tmp/rest_api_id
echo "Bootstrap complete. REST_API_ID=$REST_API_ID"
