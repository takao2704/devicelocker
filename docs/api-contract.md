# API 契約

## CheckMacStatus

Mac エージェントが現在の利用可否を確認する API。

### エンドポイント

```text
POST /v1/check
```

### リクエスト

```json
{
  "userId": "child-001",
  "deviceId": "macbook-001",
  "timestamp": 1760000000,
  "nonce": "base64url-random",
  "signature": "hex-or-base64url-hmac"
}
```

### 署名対象

署名対象文字列は初期版では以下の固定順序にする。

```text
POST
/v1/check
userId=<userId>
deviceId=<deviceId>
timestamp=<timestamp>
nonce=<nonce>
```

HMAC アルゴリズムは `HMAC-SHA256` とする。

### バリデーション

- `deviceId` が登録済みであること。
- `timestamp` がサーバー時刻から許容範囲内であること。
- `nonce` が直近に使用されていないこと。
- `signature` がデバイストークンで検証できること。

### レスポンス

```json
{
  "decision": "allow",
  "allowUntil": 1760003600,
  "serverTime": 1760000005,
  "reason": "within_allow_until",
  "retryAfterSeconds": 60,
  "policyVersion": 3
}
```

### decision

| 値 | 意味 |
| --- | --- |
| `allow` | 利用可能 |
| `deny` | 利用不可。Mac 側はロックする |

### reason

| 値 | 意味 |
| --- | --- |
| `within_allow_until` | 許可期限内 |
| `not_approved` | 承認されていない |
| `expired` | 許可期限切れ |
| `device_disabled` | 端末が無効 |
| `invalid_request` | 入力または署名が不正 |

## UpdateAllowance

保護者インターフェースから許可状態を更新する内部 API。

### 入力

```json
{
  "userId": "child-001",
  "command": "60",
  "requestedBy": "line-user-id",
  "requestedAt": 1760000000
}
```

### コマンド

| command | 更新内容 |
| --- | --- |
| `30` | 現在時刻から 30 分許可 |
| `60` | 現在時刻から 60 分許可 |
| `stop` | `IsApproved=false` にする |

### 出力

```json
{
  "userId": "child-001",
  "isApproved": true,
  "allowUntil": 1760003600,
  "updatedAt": 1760000000,
  "policyVersion": 4
}
```
