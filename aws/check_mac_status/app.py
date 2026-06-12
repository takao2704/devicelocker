import base64
import hashlib
import hmac
import json
import os
import time
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


CONTROL_TABLE = os.environ["CONTROL_TABLE"]
DEVICES_TABLE = os.environ["DEVICES_TABLE"]
NONCE_TABLE = os.environ["NONCE_TABLE"]
TIMESTAMP_TOLERANCE_SECONDS = int(os.environ.get("TIMESTAMP_TOLERANCE_SECONDS", "300"))
MAX_USAGE_DELTA_SECONDS = int(os.environ.get("MAX_USAGE_DELTA_SECONDS", "120"))
NONCE_TTL_SECONDS = int(os.environ.get("NONCE_TTL_SECONDS", "600"))

dynamodb = boto3.resource("dynamodb")
control_table = dynamodb.Table(CONTROL_TABLE)
devices_table = dynamodb.Table(DEVICES_TABLE)
nonce_table = dynamodb.Table(NONCE_TABLE)


class RequestError(Exception):
    def __init__(self, message, status_code=400, reason="invalid_request"):
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, separators=(",", ":")),
    }


def parse_body(event):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RequestError("invalid JSON body") from exc


def require_str(body, key):
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise RequestError(f"missing or invalid {key}")
    return value


def require_int(body, key):
    value = body.get(key)
    if isinstance(value, bool):
        raise RequestError(f"missing or invalid {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RequestError(f"missing or invalid {key}") from exc


def normalize_signature(signature):
    return signature.strip().rstrip("=")


def canonical_string(method, path, user_id, device_id, timestamp, usage_delta, nonce):
    return "\n".join([
        method,
        path,
        f"userId={user_id}",
        f"deviceId={device_id}",
        f"timestamp={timestamp}",
        f"usageDeltaSeconds={usage_delta}",
        f"nonce={nonce}",
    ])


def sign(secret, canonical):
    digest = hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def get_request_path(event):
    raw_path = event.get("rawPath")
    if raw_path:
        return raw_path
    return event.get("path") or "/v1/check"


def get_method(event):
    return event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "POST"


def get_device(device_id):
    result = devices_table.get_item(Key={"DeviceId": device_id})
    item = result.get("Item")
    if not item or not item.get("Enabled", True):
        raise RequestError("device disabled", status_code=403, reason="device_disabled")
    if not item.get("DeviceToken"):
        raise RequestError("device token missing", status_code=500)
    return item


def validate_request(event, now):
    body = parse_body(event)
    user_id = require_str(body, "userId")
    device_id = require_str(body, "deviceId")
    timestamp = require_int(body, "timestamp")
    usage_delta = require_int(body, "usageDeltaSeconds")
    nonce = require_str(body, "nonce")
    signature = require_str(body, "signature")

    if abs(now - timestamp) > TIMESTAMP_TOLERANCE_SECONDS:
        raise RequestError("timestamp outside tolerance")
    if usage_delta < 0 or usage_delta > MAX_USAGE_DELTA_SECONDS:
        raise RequestError("usageDeltaSeconds outside allowed range")

    device = get_device(device_id)
    device_user_id = device.get("UserId")
    if device_user_id != user_id:
        raise RequestError("user/device mismatch", status_code=403, reason="device_disabled")

    canonical = canonical_string(get_method(event), get_request_path(event), user_id, device_id, timestamp, usage_delta, nonce)
    expected = sign(device["DeviceToken"], canonical)
    if not hmac.compare_digest(expected, normalize_signature(signature)):
        raise RequestError("invalid signature", status_code=403)

    remember_nonce(device_id, nonce, timestamp, now)
    return {
        "user_id": user_id,
        "device_id": device_id,
        "usage_delta": usage_delta,
    }


def remember_nonce(device_id, nonce, timestamp, now):
    try:
        nonce_table.put_item(
            Item={
                "DeviceId": device_id,
                "Nonce": nonce,
                "Timestamp": timestamp,
                "ExpiresAt": now + NONCE_TTL_SECONDS,
            },
            ConditionExpression="attribute_not_exists(DeviceId) AND attribute_not_exists(Nonce)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise RequestError("nonce already used") from exc
        raise


def to_int(value, default=0):
    if value is None:
        return default
    return int(value)


def decide_and_update(user_id, device_id, usage_delta, now):
    result = control_table.get_item(Key={"UserId": user_id})
    item = result.get("Item")
    if not item:
        item = {
            "UserId": user_id,
            "DeviceId": device_id,
            "RemainingSeconds": Decimal(0),
            "IsApproved": False,
            "PolicyVersion": Decimal(0),
            "DeviceEnabled": True,
        }

    if not item.get("DeviceEnabled", True):
        decision = "deny"
        reason = "device_disabled"
    elif not item.get("IsApproved", False):
        decision = "deny"
        reason = "not_approved"
    else:
        remaining_before = to_int(item.get("RemainingSeconds"))
        remaining_after = max(0, remaining_before - usage_delta)
        if remaining_after <= 0:
            decision = "deny"
            reason = "time_exhausted"
        else:
            decision = "allow"
            reason = "remaining_time_available"
        item["RemainingSeconds"] = Decimal(remaining_after)

    policy_version = to_int(item.get("PolicyVersion")) + 1
    remaining = to_int(item.get("RemainingSeconds"))

    control_table.update_item(
        Key={"UserId": user_id},
        UpdateExpression=(
            "SET DeviceId = :deviceId, RemainingSeconds = :remaining, "
            "IsApproved = :approved, UpdatedAt = :updatedAt, "
            "LastUsageReportedAt = :lastUsageReportedAt, PolicyVersion = :policyVersion, "
            "DeviceEnabled = :deviceEnabled"
        ),
        ExpressionAttributeValues={
            ":deviceId": device_id,
            ":remaining": Decimal(remaining),
            ":approved": bool(item.get("IsApproved", False)),
            ":updatedAt": Decimal(now),
            ":lastUsageReportedAt": Decimal(now),
            ":policyVersion": Decimal(policy_version),
            ":deviceEnabled": bool(item.get("DeviceEnabled", True)),
        },
    )

    return {
        "decision": decision,
        "remainingSeconds": remaining,
        "serverTime": now,
        "reason": reason,
        "retryAfterSeconds": 60,
        "policyVersion": policy_version,
    }


def handler(event, context):
    now = int(time.time())
    try:
        request = validate_request(event, now)
        body = decide_and_update(request["user_id"], request["device_id"], request["usage_delta"], now)
        return response(200, body)
    except RequestError as exc:
        return response(exc.status_code, {
            "decision": "deny",
            "remainingSeconds": 0,
            "serverTime": now,
            "reason": exc.reason,
            "retryAfterSeconds": 60,
        })
