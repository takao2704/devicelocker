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
PARENT_ALLOWED_EMAILS = {
    email.strip().lower()
    for email in os.environ.get("PARENT_ALLOWED_EMAILS", "").split(",")
    if email.strip()
}
PARENT_ALLOWED_USER_IDS = [
    user_id.strip()
    for user_id in os.environ.get("PARENT_ALLOWED_USER_IDS", "child-001").split(",")
    if user_id.strip()
]
DEFAULT_PARENT_USER_ID = os.environ.get(
    "DEFAULT_PARENT_USER_ID",
    PARENT_ALLOWED_USER_IDS[0] if PARENT_ALLOWED_USER_IDS else "child-001",
)
PARENT_CHILD_NAME = os.environ.get("PARENT_CHILD_NAME", "yuuto")
MAX_PARENT_ADD_MINUTES = int(os.environ.get("MAX_PARENT_ADD_MINUTES", "360"))
PARENT_HISTORY_LIMIT = int(os.environ.get("PARENT_HISTORY_LIMIT", "20"))
PARENT_USAGE_HISTORY_LIMIT = int(os.environ.get("PARENT_USAGE_HISTORY_LIMIT", "30"))
ONLINE_WINDOW_SECONDS = int(os.environ.get("ONLINE_WINDOW_SECONDS", "180"))
PARENT_COGNITO_DOMAIN = os.environ.get("PARENT_COGNITO_DOMAIN", "")
PARENT_USER_POOL_CLIENT_ID = os.environ.get("PARENT_USER_POOL_CLIENT_ID", "")
PARENT_UI_PATH = os.environ.get("PARENT_UI_PATH", "/parent-ui")
DEFAULT_REWARD_RULES = [
    {
        "id": "calc-drill",
        "name": "計算ドリル",
        "unitName": "ページ",
        "minutesPerUnit": 5,
        "allowQuantity": True,
        "quickQuantities": [1, 2, 3, 5],
        "icon": "book-open",
    },
    {
        "id": "word-problem",
        "name": "文章題",
        "unitName": "問",
        "minutesPerUnit": 10,
        "allowQuantity": True,
        "quickQuantities": [1, 2, 3],
        "icon": "file-pen-line",
    },
    {
        "id": "marking",
        "name": "丸つけ完了",
        "unitName": "回",
        "minutesPerUnit": 10,
        "allowQuantity": False,
        "quickQuantities": [1],
        "icon": "circle-check",
    },
]

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
        "body": json.dumps(body, ensure_ascii=False, separators=(",", ":")),
    }


def html_response(status_code, html):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Cache-Control": "no-store",
        },
        "body": html,
    }


def request_origin(event):
    headers = event.get("headers") or {}
    host = headers.get("host") or headers.get("Host")
    proto = headers.get("x-forwarded-proto") or headers.get("X-Forwarded-Proto") or "https"
    if host:
        return f"{proto}://{host}"
    return ""


def parent_ui_html(event):
    path = os.path.join(os.path.dirname(__file__), "parent_ui.html")
    with open(path, encoding="utf-8") as handle:
        html = handle.read()
    origin = request_origin(event)
    redirect_uri = origin + PARENT_UI_PATH if origin else ""
    return (
        html
        .replace("__PARENT_COGNITO_DOMAIN__", PARENT_COGNITO_DOMAIN)
        .replace("__PARENT_USER_POOL_CLIENT_ID__", PARENT_USER_POOL_CLIENT_ID)
        .replace("__PARENT_REDIRECT_URI__", redirect_uri)
        .replace("__PARENT_LOGOUT_URI__", redirect_uri)
    )


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


def optional_int(body, key, default):
    value = body.get(key, default)
    if isinstance(value, bool):
        raise RequestError(f"missing or invalid {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RequestError(f"missing or invalid {key}") from exc


def parse_json_attr(value, default):
    if not value:
        return default
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return default
        return parsed if parsed is not None else default
    return value


def clamp_text(value, default, max_length):
    text = str(value or default).strip()
    if not text:
        text = default
    return text[:max_length]


def sanitize_reward_rules(rules):
    if not isinstance(rules, list) or not rules:
        raise RequestError("missing or invalid rules")
    if len(rules) > 20:
        raise RequestError("too many rules")

    sanitized = []
    seen_ids = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise RequestError("missing or invalid rules")
        rule_id = clamp_text(rule.get("id"), f"rule-{index + 1}", 64)
        if rule_id in seen_ids:
            rule_id = f"{rule_id}-{index + 1}"
        seen_ids.add(rule_id)
        try:
            minutes = int(rule.get("minutesPerUnit", 0))
        except (TypeError, ValueError) as exc:
            raise RequestError("missing or invalid minutesPerUnit") from exc
        if minutes < 1 or minutes > 180:
            raise RequestError("minutesPerUnit outside allowed range")
        quicks = rule.get("quickQuantities") or [1]
        if not isinstance(quicks, list):
            quicks = [1]
        quick_quantities = []
        for value in quicks[:8]:
            try:
                quantity = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= quantity <= 99 and quantity not in quick_quantities:
                quick_quantities.append(quantity)
        if not quick_quantities:
            quick_quantities = [1]

        sanitized.append({
            "id": rule_id,
            "name": clamp_text(rule.get("name"), "新しい項目", 24),
            "unitName": clamp_text(rule.get("unitName"), "回", 8),
            "minutesPerUnit": minutes,
            "allowQuantity": bool(rule.get("allowQuantity", True)),
            "quickQuantities": quick_quantities,
            "icon": clamp_text(rule.get("icon"), "book-open", 40),
        })
    return sanitized


def reward_rules_from_item(item):
    rules = parse_json_attr(item.get("RewardRulesJson") if item else None, DEFAULT_REWARD_RULES)
    try:
        return sanitize_reward_rules(rules)
    except (RequestError, TypeError, ValueError):
        return DEFAULT_REWARD_RULES


def history_from_item(item):
    history = parse_json_attr(item.get("ParentHistoryJson") if item else None, [])
    return history if isinstance(history, list) else []


def usage_history_from_item(item):
    history = parse_json_attr(item.get("UsageHistoryJson") if item else None, [])
    return history if isinstance(history, list) else []


def append_history(item, entry):
    history = history_from_item(item)
    next_history = [{**entry, "id": entry.get("id") or f"{entry.get('at', int(time.time()))}-{entry.get('type', 'event')}"}]
    next_history.extend(history)
    return next_history[:PARENT_HISTORY_LIMIT]


def append_usage_history(item, entry):
    history = usage_history_from_item(item)
    next_history = [{**entry, "id": entry.get("id") or f"{entry.get('at', int(time.time()))}-{entry.get('type', 'usage')}"}]
    next_history.extend(history)
    return next_history[:PARENT_USAGE_HISTORY_LIMIT]


def get_control_item(user_id):
    result = control_table.get_item(Key={"UserId": user_id})
    return result.get("Item") or {"UserId": user_id}


def minutes_from_seconds(seconds):
    seconds = max(0, int(seconds))
    if seconds == 0:
        return 0
    return (seconds + 59) // 60


def duration_label(seconds):
    seconds = max(0, int(seconds))
    minutes, remainder = divmod(seconds, 60)
    if minutes and remainder:
        return f"{minutes}分{remainder}秒"
    if minutes:
        return f"{minutes}分"
    return f"{remainder}秒"


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


def parent_claims(event):
    return (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )


def require_parent(event):
    claims = parent_claims(event)
    email = str(claims.get("email") or "").strip().lower()
    if not PARENT_ALLOWED_EMAILS:
        raise RequestError("parent email allowlist is empty", status_code=403, reason="parent_not_configured")
    if not email or email not in PARENT_ALLOWED_EMAILS:
        raise RequestError("parent email not allowed", status_code=403, reason="parent_not_allowed")
    return {"email": email, "claims": claims}


def target_user_id(event, body=None):
    query = event.get("queryStringParameters") or {}
    user_id = (body or {}).get("userId") or query.get("userId") or DEFAULT_PARENT_USER_ID
    if user_id not in PARENT_ALLOWED_USER_IDS:
        raise RequestError("userId not allowed", status_code=403, reason="user_not_allowed")
    return user_id


def control_status_body(user_id, item, now, parent_email=None):
    remaining_seconds = to_int(item.get("RemainingSeconds"))
    is_approved = bool(item.get("IsApproved", False))
    device_enabled = bool(item.get("DeviceEnabled", True))
    last_usage_at = to_int(item.get("LastUsageReportedAt"))
    online = bool(last_usage_at and now - last_usage_at <= ONLINE_WINDOW_SECONDS)
    available = is_approved and device_enabled and remaining_seconds > 0
    return {
        "userId": user_id,
        "childName": item.get("ChildName") or PARENT_CHILD_NAME,
        "remainingSeconds": remaining_seconds,
        "remainingMinutes": minutes_from_seconds(remaining_seconds),
        "isApproved": is_approved,
        "deviceEnabled": device_enabled,
        "status": "利用可" if available else "停止中",
        "online": online,
        "screen": "使用中" if available else "ロック中",
        "deviceId": item.get("DeviceId"),
        "updatedAt": to_int(item.get("UpdatedAt")),
        "lastUsageReportedAt": last_usage_at,
        "policyVersion": to_int(item.get("PolicyVersion")),
        "rewardRules": reward_rules_from_item(item),
        "history": history_from_item(item)[:PARENT_HISTORY_LIMIT],
        "usageHistory": usage_history_from_item(item)[:PARENT_USAGE_HISTORY_LIMIT],
        "parentEmail": parent_email,
        "serverTime": now,
    }


def parent_update_response(user_id, updated_item, now, parent_email):
    return control_status_body(user_id, updated_item or get_control_item(user_id), now, parent_email=parent_email)


def add_parent_minutes(user_id, body, now, parent_email):
    minutes = optional_int(body, "minutes", 0)
    if minutes < 1 or minutes > MAX_PARENT_ADD_MINUTES:
        raise RequestError("minutes outside allowed range")
    item = get_control_item(user_id)
    reason = clamp_text(body.get("reason"), "手動追加", 80)
    quantity = body.get("quantity")
    rule_id = body.get("ruleId")
    history = append_history(item, {
        "at": now,
        "title": reason,
        "detail": f"+{minutes}分を追加",
        "minutes": minutes,
        "type": "add",
        "ruleId": rule_id,
        "quantity": quantity,
        "by": parent_email,
    })
    result = control_table.update_item(
        Key={"UserId": user_id},
        UpdateExpression=(
            "SET IsApproved = :approved, UpdatedAt = :updatedAt, "
            "LastParentActionAt = :parentActionAt, LastParentActionBy = :parentEmail, "
            "ParentHistoryJson = :parentHistoryJson "
            "ADD RemainingSeconds :delta, PolicyVersion :one"
        ),
        ExpressionAttributeValues={
            ":approved": True,
            ":updatedAt": Decimal(now),
            ":parentActionAt": Decimal(now),
            ":parentEmail": parent_email,
            ":parentHistoryJson": json.dumps(history, ensure_ascii=False, separators=(",", ":")),
            ":delta": Decimal(minutes * 60),
            ":one": Decimal(1),
        },
        ReturnValues="ALL_NEW",
    )
    return parent_update_response(user_id, result.get("Attributes"), now, parent_email)


def set_parent_approval(user_id, approved, now, parent_email):
    item = get_control_item(user_id)
    history = append_history(item, {
        "at": now,
        "title": "再開" if approved else "一時停止",
        "detail": f"残り {minutes_from_seconds(to_int(item.get('RemainingSeconds')))}分",
        "minutes": 0,
        "type": "resume" if approved else "pause",
        "by": parent_email,
    })
    result = control_table.update_item(
        Key={"UserId": user_id},
        UpdateExpression=(
            "SET IsApproved = :approved, UpdatedAt = :updatedAt, "
            "LastParentActionAt = :parentActionAt, LastParentActionBy = :parentEmail, "
            "ParentHistoryJson = :parentHistoryJson "
            "ADD PolicyVersion :one"
        ),
        ExpressionAttributeValues={
            ":approved": approved,
            ":updatedAt": Decimal(now),
            ":parentActionAt": Decimal(now),
            ":parentEmail": parent_email,
            ":parentHistoryJson": json.dumps(history, ensure_ascii=False, separators=(",", ":")),
            ":one": Decimal(1),
        },
        ReturnValues="ALL_NEW",
    )
    return parent_update_response(user_id, result.get("Attributes"), now, parent_email)


def update_reward_rules(user_id, body, now, parent_email):
    rules = sanitize_reward_rules(body.get("rules"))
    item = get_control_item(user_id)
    history = append_history(item, {
        "at": now,
        "title": "報酬ルールを更新",
        "detail": f"{len(rules)}項目",
        "minutes": 0,
        "type": "rules",
        "by": parent_email,
    })
    result = control_table.update_item(
        Key={"UserId": user_id},
        UpdateExpression=(
            "SET RewardRulesJson = :rewardRulesJson, UpdatedAt = :updatedAt, "
            "LastParentActionAt = :parentActionAt, LastParentActionBy = :parentEmail, "
            "ParentHistoryJson = :parentHistoryJson "
            "ADD PolicyVersion :one"
        ),
        ExpressionAttributeValues={
            ":rewardRulesJson": json.dumps(rules, ensure_ascii=False, separators=(",", ":")),
            ":updatedAt": Decimal(now),
            ":parentActionAt": Decimal(now),
            ":parentEmail": parent_email,
            ":parentHistoryJson": json.dumps(history, ensure_ascii=False, separators=(",", ":")),
            ":one": Decimal(1),
        },
        ReturnValues="ALL_NEW",
    )
    return parent_update_response(user_id, result.get("Attributes"), now, parent_email)


def handle_parent_request(event, method, path, now):
    parent = require_parent(event)
    body = parse_body(event) if method in ("POST", "PUT", "PATCH") else {}
    user_id = target_user_id(event, body)

    if method == "GET" and path == "/v1/parent/status":
        return control_status_body(user_id, get_control_item(user_id), now, parent_email=parent["email"])
    if method == "POST" and path == "/v1/parent/add-time":
        return add_parent_minutes(user_id, body, now, parent["email"])
    if method == "POST" and path == "/v1/parent/stop":
        return set_parent_approval(user_id, False, now, parent["email"])
    if method == "POST" and path == "/v1/parent/start":
        return set_parent_approval(user_id, True, now, parent["email"])
    if method == "GET" and path == "/v1/parent/reward-rules":
        return {
            "userId": user_id,
            "rewardRules": reward_rules_from_item(get_control_item(user_id)),
            "serverTime": now,
        }
    if method == "PUT" and path == "/v1/parent/reward-rules":
        return update_reward_rules(user_id, body, now, parent["email"])
    raise RequestError("not found", status_code=404, reason="not_found")


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

    consumed_seconds = 0
    if not item.get("DeviceEnabled", True):
        decision = "deny"
        reason = "device_disabled"
    elif not item.get("IsApproved", False):
        decision = "deny"
        reason = "not_approved"
    else:
        remaining_before = to_int(item.get("RemainingSeconds"))
        remaining_after = max(0, remaining_before - usage_delta)
        consumed_seconds = max(0, remaining_before - remaining_after)
        if remaining_after <= 0:
            decision = "deny"
            reason = "time_exhausted"
        else:
            decision = "allow"
            reason = "remaining_time_available"
        item["RemainingSeconds"] = Decimal(remaining_after)

    policy_version = to_int(item.get("PolicyVersion")) + 1
    remaining = to_int(item.get("RemainingSeconds"))

    update_expression = (
        "SET DeviceId = :deviceId, RemainingSeconds = :remaining, "
        "IsApproved = :approved, UpdatedAt = :updatedAt, "
        "LastUsageReportedAt = :lastUsageReportedAt, PolicyVersion = :policyVersion, "
        "DeviceEnabled = :deviceEnabled"
    )
    expression_values = {
        ":deviceId": device_id,
        ":remaining": Decimal(remaining),
        ":approved": bool(item.get("IsApproved", False)),
        ":updatedAt": Decimal(now),
        ":lastUsageReportedAt": Decimal(now),
        ":policyVersion": Decimal(policy_version),
        ":deviceEnabled": bool(item.get("DeviceEnabled", True)),
    }
    if consumed_seconds > 0:
        update_expression += ", UsageHistoryJson = :usageHistoryJson"
        usage_history = append_usage_history(item, {
            "at": now,
            "title": "Mac利用",
            "detail": f"{duration_label(consumed_seconds)}を消化",
            "minutes": -minutes_from_seconds(consumed_seconds),
            "seconds": consumed_seconds,
            "type": "usage",
            "deviceId": device_id,
            "remainingSeconds": remaining,
        })
        expression_values[":usageHistoryJson"] = json.dumps(
            usage_history,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    control_table.update_item(
        Key={"UserId": user_id},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values,
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
    path = get_request_path(event)
    method = get_method(event)
    if method == "GET" and path.rstrip("/") == PARENT_UI_PATH:
        return html_response(200, parent_ui_html(event))
    if method == "OPTIONS":
        return response(204, {})
    try:
        if path.startswith("/v1/parent/"):
            return response(200, handle_parent_request(event, method, path, now))
        request = validate_request(event, now)
        body = decide_and_update(request["user_id"], request["device_id"], request["usage_delta"], now)
        return response(200, body)
    except RequestError as exc:
        if path.startswith("/v1/parent/"):
            return response(exc.status_code, {
                "error": exc.reason,
                "message": str(exc),
                "serverTime": now,
            })
        return response(exc.status_code, {
            "decision": "deny",
            "remainingSeconds": 0,
            "serverTime": now,
            "reason": exc.reason,
            "retryAfterSeconds": 60,
        })
