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
| `TokenHash` | String | デバイストークンのハッシュ |
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
  "last_server_time": 1760000005,
  "last_decision": "allow",
  "remaining_seconds": 1740,
  "last_usage_reported_at": 1760000005,
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
  "user_id": "child-001",
  "device_id": "macbook-001",
  "grace_period_seconds": 60,
  "retry_after_seconds": 60
}
```

デバイストークン:

```text
/Library/Application Support/DeviceLocker/device.token
```
