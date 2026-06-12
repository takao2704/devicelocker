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
PARAMETER_OVERRIDES=""

add_parameter() {
  key="$1"
  value="$2"
  if [ -n "$value" ]; then
    PARAMETER_OVERRIDES="$PARAMETER_OVERRIDES $key=$value"
  fi
}

add_parameter "ParentAllowedEmails" "${PARENT_ALLOWED_EMAILS:-}"
add_parameter "ParentAllowedUserIds" "${PARENT_ALLOWED_USER_IDS:-}"
add_parameter "ParentChildName" "${PARENT_CHILD_NAME:-}"
add_parameter "ParentAuthDomainPrefix" "${PARENT_AUTH_DOMAIN_PREFIX:-}"
add_parameter "ParentCallbackUrls" "${PARENT_CALLBACK_URLS:-}"
add_parameter "ParentLogoutUrls" "${PARENT_LOGOUT_URLS:-}"
add_parameter "GoogleOAuthClientId" "${GOOGLE_OAUTH_CLIENT_ID:-}"
add_parameter "GoogleOAuthClientSecret" "${GOOGLE_OAUTH_CLIENT_SECRET:-}"

PARAMETER_ARGS=""
if [ -n "$PARAMETER_OVERRIDES" ]; then
  PARAMETER_ARGS="--parameter-overrides $PARAMETER_OVERRIDES"
fi

aws cloudformation deploy \
  $REGION_ARGS \
  --stack-name "$STACK_NAME" \
  --template-file "$TEMPLATE" \
  --capabilities CAPABILITY_IAM \
  $PARAMETER_ARGS

aws lambda update-function-code \
  $REGION_ARGS \
  --function-name DeviceLockerCheckMacStatus \
  --zip-file "fileb://$ZIP_PATH" >/dev/null

aws cloudformation describe-stacks \
  $REGION_ARGS \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --output table
