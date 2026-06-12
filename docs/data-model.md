# データモデル

## DynamoDB: DeviceLockerControl

初期版は 1 テーブル構成とし、ユーザーまたは端末単位の残り利用可能時間を保持する。

### キー

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `UserId` | String | 子どもまたは端末利用者の識別子 |

### 属性

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `UserId` | String | パーティションキー |
| `DeviceId` | String | 初期版では代表端末 ID |
| `RemainingSeconds` | Number | 残り利用可能秒数 |
| `IsApproved` | Boolean | 利用承認中かどうか |
| `UpdatedAt` | Number | 最終更新時刻。Unix epoch seconds |
| `LastUsageReportedAt` | Number | Mac から最後に利用時間が報告された時刻 |
| `PolicyVersion` | Number | ポリシー更新ごとに増加するバージョン |
| `DeviceEnabled` | Boolean | 端末が有効かどうか |
| `RewardRulesJson` | String | 親 Web UI の報酬ルール JSON |
| `ParentHistoryJson` | String | 親 Web UI の最近の操作履歴 JSON |
| `LastParentActionAt` | Number | 親 Web UI から最後に操作した時刻 |
| `LastParentActionBy` | String | 最後に操作した親のメールアドレス |

`RewardRulesJson` は以下の配列を JSON 文字列として保存する。

```json
[
  {
    "id": "calc-drill",
    "name": "計算ドリル",
    "unitName": "ページ",
    "minutesPerUnit": 5,
    "allowQuantity": true,
    "quickQuantities": [1, 2, 3, 5],
    "icon": "book-open"
  }
]
```

MVP では親 Web UI と CLI の両方が同じ `RemainingSeconds` / `IsApproved` を更新する。報酬ルールと履歴は親 Web UI 専用の補助属性として扱う。

## DynamoDB: DeviceLockerDevices

HMAC 署名検証のため、デバイス情報は別テーブルに分離する案を推奨する。

### キー

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `DeviceId` | String | 端末識別子 |

### 属性

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `DeviceId` | String | パーティションキー |
| `UserId` | String | 紐づくユーザー |
| `DeviceToken` | String | MVP 用の HMAC 共有秘密 |
| `TokenHash` | String | 次フェーズで使うデバイストークンのハッシュ |
| `TokenSecretRef` | String | Secrets Manager などに置く場合の参照 |
| `Enabled` | Boolean | 端末の有効状態 |
| `CreatedAt` | Number | 登録時刻 |
| `UpdatedAt` | Number | 更新時刻 |

## DynamoDB: DeviceLockerNonce

リプレイ防止のため、使用済み nonce を短期間だけ保持する。

### キー

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `DeviceId` | String | パーティションキー |
| `Nonce` | String | ソートキー |

### 属性

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `ExpiresAt` | Number | DynamoDB TTL 用の失効時刻 |
| `Timestamp` | Number | リクエストに含まれる時刻 |

## ローカル状態ファイル

保存先:

```text
/var/db/devicelocker/state.json
```

内容:

```json
{
  "last_success_at": 1760000005,
  "last_success_local_at": 1760000005,
  "last_server_time": 1760000005,
  "last_decision": "allow",
  "remaining_seconds": 1740,
  "last_usage_reported_at": 1760000005,
  "last_usage_reported_local_at": 1760000005,
  "usage_baseline_local_at": 1760000005,
  "last_console_user": "yuuto",
  "last_skipped_local_at": null,
  "last_skip_reason": null,
  "screen_locked": false,
  "last_screen_locked_local_at": null,
  "grace_until": 1760000065,
  "locked_at": null,
  "policy_version": 3
}
```

設定ファイル:

```text
/Library/Application Support/DeviceLocker/config.json
```

```json
{
  "api_base_url": "https://example.execute-api.ap-northeast-1.amazonaws.com",
  "check_path": "/v1/check",
  "user_id": "child-001",
  "device_id": "macbook-001",
  "monitored_user_name": "yuuto",
  "token_path": "/Library/Application Support/DeviceLocker/device.token",
  "state_path": "/var/db/devicelocker/state.json",
  "lock_command": "/usr/local/sbin/devicelocker-lock",
  "grace_period_seconds": 60,
  "timeout_seconds": 5,
  "max_usage_delta_seconds": 120
}
```

デバイストークン:

```text
/Library/Application Support/DeviceLocker/device.token
```
