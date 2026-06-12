#!/bin/sh
set -eu

COMMAND="${1:-}"
VALUE="${2:-}"
USER_ID="${USER_ID:-child-001}"
STACK_NAME="${STACK_NAME:-devicelocker-mvp}"
REGION_ARGS=""
export AWS_PAGER="${AWS_PAGER:-}"

if [ -z "$COMMAND" ]; then
  echo "Usage: $0 +minutes|set-seconds seconds|stop|start|status" >&2
  exit 2
fi

if [ -n "${AWS_REGION:-}" ]; then
  REGION_ARGS="--region $AWS_REGION"
fi

CONTROL_TABLE="$(aws cloudformation describe-stacks $REGION_ARGS --stack-name "$STACK_NAME" --query "Stacks[0].Outputs[?OutputKey=='ControlTableName'].OutputValue" --output text)"
NOW="$(date +%s)"

case "$COMMAND" in
  +*)
    minutes="${COMMAND#+}"
    delta_seconds="$((minutes * 60))"
    aws dynamodb update-item $REGION_ARGS \
      --table-name "$CONTROL_TABLE" \
      --key "{\"UserId\":{\"S\":\"$USER_ID\"}}" \
      --update-expression "SET IsApproved = :approved, UpdatedAt = :now ADD RemainingSeconds :delta, PolicyVersion :one" \
      --expression-attribute-values "{
        \":approved\": {\"BOOL\": true},
        \":now\": {\"N\": \"$NOW\"},
        \":delta\": {\"N\": \"$delta_seconds\"},
        \":one\": {\"N\": \"1\"}
      }" \
      --return-values ALL_NEW
    ;;
  stop)
    aws dynamodb update-item $REGION_ARGS \
      --table-name "$CONTROL_TABLE" \
      --key "{\"UserId\":{\"S\":\"$USER_ID\"}}" \
      --update-expression "SET IsApproved = :approved, UpdatedAt = :now ADD PolicyVersion :one" \
      --expression-attribute-values "{
        \":approved\": {\"BOOL\": false},
        \":now\": {\"N\": \"$NOW\"},
        \":one\": {\"N\": \"1\"}
      }" \
      --return-values ALL_NEW
    ;;
  start)
    aws dynamodb update-item $REGION_ARGS \
      --table-name "$CONTROL_TABLE" \
      --key "{\"UserId\":{\"S\":\"$USER_ID\"}}" \
      --update-expression "SET IsApproved = :approved, UpdatedAt = :now ADD PolicyVersion :one" \
      --expression-attribute-values "{
        \":approved\": {\"BOOL\": true},
        \":now\": {\"N\": \"$NOW\"},
        \":one\": {\"N\": \"1\"}
      }" \
      --return-values ALL_NEW
    ;;
  set-seconds)
    if [ -z "$VALUE" ]; then
      echo "Usage: $0 set-seconds seconds" >&2
      exit 2
    fi
    aws dynamodb update-item $REGION_ARGS \
      --table-name "$CONTROL_TABLE" \
      --key "{\"UserId\":{\"S\":\"$USER_ID\"}}" \
      --update-expression "SET IsApproved = :approved, RemainingSeconds = :remaining, UpdatedAt = :now ADD PolicyVersion :one" \
      --expression-attribute-values "{
        \":approved\": {\"BOOL\": true},
        \":remaining\": {\"N\": \"$VALUE\"},
        \":now\": {\"N\": \"$NOW\"},
        \":one\": {\"N\": \"1\"}
      }" \
      --return-values ALL_NEW
    ;;
  status)
    aws dynamodb get-item $REGION_ARGS \
      --table-name "$CONTROL_TABLE" \
      --key "{\"UserId\":{\"S\":\"$USER_ID\"}}"
    ;;
  *)
    echo "Usage: $0 +minutes|set-seconds seconds|stop|start|status" >&2
    exit 2
    ;;
esac
