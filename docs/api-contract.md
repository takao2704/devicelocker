# API 契約

## CheckMacStatus

Mac エージェントが現在の利用可否を確認し、前回チェックからの利用時間を報告する API。

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
  "usageDeltaSeconds": 60,
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
usageDeltaSeconds=<usageDeltaSeconds>
nonce=<nonce>
```

HMAC アルゴリズムは `HMAC-SHA256` とする。

### バリデーション

- `deviceId` が登録済みであること。
- `timestamp` がサーバー時刻から許容範囲内であること。
- `usageDeltaSeconds` が許容範囲内であること。
- `nonce` が直近に使用されていないこと。
- `signature` がデバイストークンで検証できること。

### レスポンス

```json
{
  "decision": "allow",
  "remainingSeconds": 1740,
  "serverTime": 1760000005,
  "reason": "remaining_time_available",
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
| `remaining_time_available` | 残り利用可能時間がある |
| `not_approved` | 承認されていない |
| `time_exhausted` | 残り利用可能時間がゼロ |
| `device_disabled` | 端末が無効 |
| `invalid_request` | 入力または署名が不正 |

## AddUsageCredit

保護者インターフェースから利用可能時間を追加する内部 API。MVP では親の手動操作を前提にする。

### 入力

```json
{
  "userId": "child-001",
  "command": "+60",
  "requestedBy": "line-user-id",
  "requestedAt": 1760000000
}
```

### コマンド

| command | 更新内容 |
| --- | --- |
| `+30` | 残り利用可能時間に 30 分追加 |
| `+60` | 残り利用可能時間に 60 分追加 |
| `stop` | `IsApproved=false` にする |

### 出力

```json
{
  "userId": "child-001",
  "isApproved": true,
  "remainingSeconds": 3600,
  "updatedAt": 1760000000,
  "policyVersion": 4
}
```

## Parent Web API

親向け Web UI から呼び出す API。`Authorization` header に Cognito ID token を `Bearer` 形式で付ける。

Lambda は API Gateway JWT authorizer が検証した claims から `email` を取り出し、環境変数 `PARENT_ALLOWED_EMAILS` の許可リストと照合する。

### GET /v1/parent/status

現在の状態、報酬ルール、最近の親操作履歴、Mac 利用による時間消化履歴を返す。

```json
{
  "userId": "child-001",
  "childName": "child",
  "remainingSeconds": 1800,
  "remainingMinutes": 30,
  "isApproved": true,
  "deviceEnabled": true,
  "status": "利用可",
  "online": true,
  "screen": "使用中",
  "policyVersion": 12,
  "rewardRules": [],
  "history": [],
  "usageHistory": [
    {
      "at": 1760000000,
      "startedAt": 1759999940,
      "title": "Mac利用",
      "detail": "1分を消化",
      "minutes": -1,
      "seconds": 60,
      "type": "usage",
      "deviceId": "macbook-001",
      "remainingSeconds": 1740
    }
  ],
  "parentEmail": "parent@example.com",
  "serverTime": 1760000000
}
```

### POST /v1/parent/add-time

残り時間を追加し、`IsApproved=true` に戻す。

```json
{
  "userId": "child-001",
  "minutes": 15,
  "reason": "計算ドリル 3ページ",
  "ruleId": "calc-drill",
  "quantity": 3
}
```

レスポンスは `GET /v1/parent/status` と同じ形式。

### POST /v1/parent/stop

`IsApproved=false` にする。次回の Mac agent check で `deny` になり、child が使用中ならロックされる。

```json
{
  "userId": "child-001"
}
```

### POST /v1/parent/start

`IsApproved=true` にする。

```json
{
  "userId": "child-001"
}
```

### GET /v1/parent/reward-rules

親が編集した報酬ルールだけを取得する。

```json
{
  "userId": "child-001",
  "rewardRules": [
    {
      "id": "calc-drill",
      "name": "計算ドリル",
      "unitName": "ページ",
      "minutesPerUnit": 5,
      "allowQuantity": true,
      "quickQuantities": [1, 2, 3, 5],
      "icon": "book-open"
    }
  ],
  "serverTime": 1760000000
}
```

### PUT /v1/parent/reward-rules

報酬ルールを保存する。

```json
{
  "userId": "child-001",
  "rules": [
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
}
```
