#!/bin/sh
set -eu

USER_ID="${USER_ID:-child-001}"
DEVICE_ID="${DEVICE_ID:-macbook-001}"
DEVICE_TOKEN="${DEVICE_TOKEN:-}"
REMAINING_SECONDS="${REMAINING_SECONDS:-600}"
STACK_NAME="${STACK_NAME:-devicelocker-mvp}"
REGION_ARGS=""

if [ -z "$DEVICE_TOKEN" ]; then
  echo "DEVICE_TOKEN is required." >&2
  echo "Example:" >&2
  echo "  DEVICE_TOKEN=\$(openssl rand -base64 32) $0" >&2
  exit 1
fi

if [ -n "${AWS_REGION:-}" ]; then
  REGION_ARGS="--region $AWS_REGION"
fi

CONTROL_TABLE="$(aws cloudformation describe-stacks $REGION_ARGS --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='ControlTableName'].OutputValue" --output text)"
DEVICES_TABLE="$(aws cloudformation describe-stacks $REGION_ARGS --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='DevicesTableName'].OutputValue" --output text)"
NOW="$(date +%s)"

aws dynamodb put-item $REGION_ARGS \
  --table-name "$DEVICES_TABLE" \
  --item "{
    \"DeviceId\": {\"S\": \"$DEVICE_ID\"},
    \"UserId\": {\"S\": \"$USER_ID\"},
    \"DeviceToken\": {\"S\": \"$DEVICE_TOKEN\"},
    \"Enabled\": {\"BOOL\": true},
    \"CreatedAt\": {\"N\": \"$NOW\"},
    \"UpdatedAt\": {\"N\": \"$NOW\"}
  }" >/dev/null

aws dynamodb put-item $REGION_ARGS \
  --table-name "$CONTROL_TABLE" \
  --item "{
    \"UserId\": {\"S\": \"$USER_ID\"},
    \"DeviceId\": {\"S\": \"$DEVICE_ID\"},
    \"RemainingSeconds\": {\"N\": \"$REMAINING_SECONDS\"},
    \"IsApproved\": {\"BOOL\": true},
    \"UpdatedAt\": {\"N\": \"$NOW\"},
    \"LastUsageReportedAt\": {\"N\": \"0\"},
    \"PolicyVersion\": {\"N\": \"1\"},
    \"DeviceEnabled\": {\"BOOL\": true}
  }" >/dev/null

echo "Seeded $USER_ID / $DEVICE_ID"
echo "Device token:"
echo "$DEVICE_TOKEN"
