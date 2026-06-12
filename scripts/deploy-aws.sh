#!/bin/sh
set -eu

STACK_NAME="${STACK_NAME:-devicelocker-mvp}"
REGION_ARGS=""

if [ -n "${AWS_REGION:-}" ]; then
  REGION_ARGS="--region $AWS_REGION"
fi

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TEMPLATE="$ROOT/aws/template.json"
ZIP_PATH="$("$ROOT/scripts/package-aws.sh")"

aws cloudformation deploy \
  $REGION_ARGS \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_IAM

aws lambda update-function-code \
  $REGION_ARGS \
  --function-name DeviceLockerCheckMacStatus \
  --zip-file "fileb://$ZIP_PATH" >/dev/null

aws cloudformation describe-stacks \
  $REGION_ARGS \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --output table
