import base64
import importlib.util
import json
import os
import sys
import time
import types
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "aws" / "check_mac_status" / "app.py"


class FakeClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeTable:
    def __init__(self, items=None):
        self.items = items or {}
        self.puts = []
        self.updates = []

    def get_item(self, Key):
        key = tuple(Key.items())
        item = self.items.get(key)
        return {"Item": deepcopy(item)} if item else {}

    def put_item(self, Item, ConditionExpression=None):
        key = tuple((k, Item[k]) for k in ("DeviceId", "Nonce") if k in Item)
        if key in self.items:
            raise FakeClientError("ConditionalCheckFailedException")
        self.items[key] = deepcopy(Item)
        self.puts.append(Item)

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues, ReturnValues=None):
        key = tuple(Key.items())
        item = self.items.setdefault(key, dict(Key))
        if ":deviceId" in ExpressionAttributeValues:
            item["DeviceId"] = ExpressionAttributeValues[":deviceId"]
        if ":remaining" in ExpressionAttributeValues:
            item["RemainingSeconds"] = ExpressionAttributeValues[":remaining"]
        if ":delta" in ExpressionAttributeValues:
            item["RemainingSeconds"] = item.get("RemainingSeconds", 0) + ExpressionAttributeValues[":delta"]
        if ":approved" in ExpressionAttributeValues:
            item["IsApproved"] = ExpressionAttributeValues[":approved"]
        if ":updatedAt" in ExpressionAttributeValues:
            item["UpdatedAt"] = ExpressionAttributeValues[":updatedAt"]
        if ":lastUsageReportedAt" in ExpressionAttributeValues:
            item["LastUsageReportedAt"] = ExpressionAttributeValues[":lastUsageReportedAt"]
        if ":policyVersion" in ExpressionAttributeValues:
            item["PolicyVersion"] = ExpressionAttributeValues[":policyVersion"]
        if ":one" in ExpressionAttributeValues and ":policyVersion" not in ExpressionAttributeValues:
            item["PolicyVersion"] = item.get("PolicyVersion", 0) + ExpressionAttributeValues[":one"]
        if ":deviceEnabled" in ExpressionAttributeValues:
            item["DeviceEnabled"] = ExpressionAttributeValues[":deviceEnabled"]
        if ":parentActionAt" in ExpressionAttributeValues:
            item["LastParentActionAt"] = ExpressionAttributeValues[":parentActionAt"]
        if ":parentEmail" in ExpressionAttributeValues:
            item["LastParentActionBy"] = ExpressionAttributeValues[":parentEmail"]
        if ":parentHistoryJson" in ExpressionAttributeValues:
            item["ParentHistoryJson"] = ExpressionAttributeValues[":parentHistoryJson"]
        if ":rewardRulesJson" in ExpressionAttributeValues:
            item["RewardRulesJson"] = ExpressionAttributeValues[":rewardRulesJson"]
        self.updates.append((Key, ExpressionAttributeValues))
        return {"Attributes": deepcopy(item)} if ReturnValues == "ALL_NEW" else {}


class FakeDynamoResource:
    def __init__(self, tables):
        self.tables = tables

    def Table(self, name):
        return self.tables[name]


def load_module(tables, extra_env=None):
    boto3 = types.SimpleNamespace(resource=lambda name: FakeDynamoResource(tables))
    botocore = types.ModuleType("botocore")
    exceptions = types.ModuleType("botocore.exceptions")
    exceptions.ClientError = FakeClientError
    sys.modules["boto3"] = boto3
    sys.modules["botocore"] = botocore
    sys.modules["botocore.exceptions"] = exceptions
    env = {
        "CONTROL_TABLE": "control",
        "DEVICES_TABLE": "devices",
        "NONCE_TABLE": "nonce",
    }
    if extra_env:
        env.update(extra_env)
    with mock.patch.dict(os.environ, env, clear=False):
        spec = importlib.util.spec_from_file_location("check_mac_status_app", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def signature(module, secret, timestamp, usage_delta, nonce):
    canonical = module.canonical_string("POST", "/v1/check", "child-001", "macbook-001", timestamp, usage_delta, nonce)
    return module.sign(secret, canonical)


def event(module, secret="secret", timestamp=None, usage_delta=60, nonce="nonce-1"):
    timestamp = timestamp or int(time.time())
    body = {
        "userId": "child-001",
        "deviceId": "macbook-001",
        "timestamp": timestamp,
        "usageDeltaSeconds": usage_delta,
        "nonce": nonce,
        "signature": signature(module, secret, timestamp, usage_delta, nonce),
    }
    return {
        "rawPath": "/v1/check",
        "requestContext": {"http": {"method": "POST"}},
        "body": json.dumps(body),
    }


def parent_event(path, method="GET", body=None, email="parent@example.com"):
    return {
        "rawPath": path,
        "requestContext": {
            "http": {"method": method},
            "authorizer": {
                "jwt": {
                    "claims": {
                        "email": email,
                        "token_use": "id",
                    }
                }
            },
        },
        "body": json.dumps(body or {}),
    }


class CheckMacStatusLambdaTests(unittest.TestCase):
    def setUp(self):
        self.tables = {
            "control": FakeTable({
                (("UserId", "child-001"),): {
                    "UserId": "child-001",
                    "DeviceId": "macbook-001",
                    "RemainingSeconds": 120,
                    "IsApproved": True,
                    "PolicyVersion": 1,
                    "DeviceEnabled": True,
                }
            }),
            "devices": FakeTable({
                (("DeviceId", "macbook-001"),): {
                    "DeviceId": "macbook-001",
                    "UserId": "child-001",
                    "DeviceToken": "secret",
                    "Enabled": True,
                }
            }),
            "nonce": FakeTable(),
        }
        self.module = load_module(self.tables, {
            "PARENT_ALLOWED_EMAILS": "parent@example.com",
            "PARENT_ALLOWED_USER_IDS": "child-001",
        })

    def response_body(self, result):
        return json.loads(result["body"])

    def test_allow_decrements_remaining_time(self):
        result = self.module.handler(event(self.module, usage_delta=60), None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["decision"], "allow")
        self.assertEqual(body["remainingSeconds"], 60)

    def test_time_exhausted_denies(self):
        result = self.module.handler(event(self.module, usage_delta=120), None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["decision"], "deny")
        self.assertEqual(body["reason"], "time_exhausted")
        self.assertEqual(body["remainingSeconds"], 0)

    def test_invalid_signature_rejected(self):
        bad_event = event(self.module, secret="wrong")
        result = self.module.handler(bad_event, None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 403)
        self.assertEqual(body["decision"], "deny")
        self.assertEqual(body["reason"], "invalid_request")

    def test_reused_nonce_rejected(self):
        self.module.handler(event(self.module, nonce="same"), None)
        result = self.module.handler(event(self.module, nonce="same"), None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(body["reason"], "invalid_request")

    def test_parent_status_requires_allowed_email(self):
        result = self.module.handler(parent_event("/v1/parent/status", email="other@example.com"), None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 403)
        self.assertEqual(body["error"], "parent_not_allowed")

    def test_parent_add_time_updates_control_record(self):
        result = self.module.handler(parent_event(
            "/v1/parent/add-time",
            method="POST",
            body={
                "minutes": 15,
                "reason": "計算ドリル 3ページ",
                "ruleId": "calc-drill",
                "quantity": 3,
            },
        ), None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["remainingSeconds"], 1020)
        self.assertEqual(body["remainingMinutes"], 17)
        self.assertTrue(body["isApproved"])
        self.assertEqual(body["history"][0]["title"], "計算ドリル 3ページ")
        self.assertEqual(body["history"][0]["minutes"], 15)

    def test_parent_reward_rules_are_saved(self):
        rules = [
            {
                "id": "hundred-math",
                "name": "百ます計算",
                "unitName": "枚",
                "minutesPerUnit": 7,
                "allowQuantity": True,
                "quickQuantities": [1, 2, 4],
                "icon": "book-open",
            }
        ]
        result = self.module.handler(parent_event(
            "/v1/parent/reward-rules",
            method="PUT",
            body={"rules": rules},
        ), None)
        body = self.response_body(result)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["rewardRules"], rules)
        saved = self.tables["control"].items[(("UserId", "child-001"),)]["RewardRulesJson"]
        self.assertEqual(json.loads(saved), rules)


if __name__ == "__main__":
    unittest.main()
