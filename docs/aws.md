# AWS MVP

AWS 側は CloudFormation と Python Lambda で構成する。

## 構成

- HTTP API: `POST /v1/check`
- Lambda: `DeviceLockerCheckMacStatus`
- DynamoDB: `DeviceLockerControl`
- DynamoDB: `DeviceLockerDevices`
- DynamoDB: `DeviceLockerNonce`

## デプロイ

AWS CLI の認証とリージョン設定を済ませてから実行する。

```sh
AWS_REGION=ap-northeast-1 scripts/deploy-aws.sh
```

別名の stack にしたい場合:

```sh
STACK_NAME=devicelocker-dev AWS_REGION=ap-northeast-1 scripts/deploy-aws.sh
```

`deploy-aws.sh` は CloudFormation stack を作成または更新し、その後 `aws/check_mac_status/app.py` を zip 化して Lambda コードを更新する。

親向け Web UI を Google アカウント認証で使う場合は、Cognito Hosted UI 用の domain prefix を決めて 2 段階でデプロイする。prefix はリージョン内で一意にする。

1 回目は Google OAuth client をまだ指定せず、Cognito domain と Google 登録用 URI を作る。

```sh
export AWS_REGION=ap-northeast-1
export PARENT_ALLOWED_EMAILS="parent@example.com"
export PARENT_ALLOWED_USER_IDS="child-001"
export PARENT_CHILD_NAME="child"
export PARENT_AUTH_DOMAIN_PREFIX="devicelocker-parent-unique-name"
export PARENT_CALLBACK_URLS="http://127.0.0.1:4173/"
export PARENT_LOGOUT_URLS="http://127.0.0.1:4173/"
scripts/deploy-aws.sh
```

CloudFormation output の `GoogleAuthorizedRedirectUri` を Google Cloud Console の OAuth client に Authorized redirect URI として登録する。

```text
https://<cognito-domain>.auth.ap-northeast-1.amazoncognito.com/oauth2/idpresponse
```

Google OAuth client ID / secret を取得したら、2 回目のデプロイで Google provider を有効にする。

```sh
export GOOGLE_OAUTH_CLIENT_ID="Google OAuth client ID"
export GOOGLE_OAUTH_CLIENT_SECRET="Google OAuth client secret"
scripts/deploy-aws.sh
```

Amplify Hosting に載せる場合は、Amplify 側のURLが決まった後に `PARENT_CALLBACK_URLS` と `PARENT_LOGOUT_URLS` を本番URLへ変更して再デプロイする。例:

```sh
export PARENT_CALLBACK_URLS="https://main.example.amplifyapp.com/"
export PARENT_LOGOUT_URLS="https://main.example.amplifyapp.com/"
scripts/deploy-aws.sh
```

Amplify Hosting の環境変数には以下を設定する。`amplify.yml` が `prototypes/parent-time-ui/src/config.js` を生成する。

| 環境変数 | 値 |
| --- | --- |
| `DEVICELOCKER_API_BASE_URL` | CloudFormation output `ApiEndpoint` |
| `DEVICELOCKER_COGNITO_DOMAIN` | CloudFormation output `ParentCognitoDomain` |
| `DEVICELOCKER_COGNITO_CLIENT_ID` | CloudFormation output `ParentUserPoolClientId` |
| `DEVICELOCKER_REDIRECT_URI` | `https://main.example.amplifyapp.com/` |
| `DEVICELOCKER_LOGOUT_URI` | `https://main.example.amplifyapp.com/` |
| `DEVICELOCKER_USER_ID` | `child-001` |

親 Web UI は Cognito の ID token を `Authorization: Bearer ...` として親APIへ送る。API Gateway の JWT authorizer が署名・issuer・audience を検証し、Lambda が `email` claim を `PARENT_ALLOWED_EMAILS` と照合する。

### API Gateway 配信

Amplify Hosting が使えない場合でも、同じ親 Web UI を API Gateway 経由で配信できる。

```text
https://<api-id>.execute-api.ap-northeast-1.amazonaws.com/parent-ui
```

`scripts/package-aws.sh` は `prototypes/parent-time-ui` の HTML/CSS/JS を単一の `parent_ui.html` にまとめ、Lambda zip に同梱する。`GET /parent-ui` は認証なしで画面だけを返し、実際の親操作 API `/v1/parent/*` は Cognito JWT authorizer で保護する。

この方式を使う場合は Cognito callback/logout URL に `/parent-ui` のURLを追加する。

## 初期データ投入

```sh
DEVICE_TOKEN="$(openssl rand -base64 32)" \
REMAINING_SECONDS=600 \
AWS_REGION=ap-northeast-1 \
scripts/seed-aws-device.sh
```

表示された `DEVICE_TOKEN` を Mac 側の以下に保存する。

```text
/Library/Application Support/DeviceLocker/device.token
```

Mac 側設定のインストール:

```sh
sudo API_BASE_URL="https://example.execute-api.ap-northeast-1.amazonaws.com" \
  DEVICE_TOKEN="表示された device token" \
  scripts/install-device-config.sh
```

`API_BASE_URL` は deploy 後の CloudFormation output `ApiEndpoint` を使う。

## 手動の時間追加

MVP では親の手動操作として DynamoDB を直接更新する。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh +30
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh status
```

残り時間を試験用に直接セット:

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh set-seconds 60
```

自然ゼロ試験では、過去ログと混ざらないように別ターミナルで以下を使う。

```sh
tail -n 0 -f /var/log/devicelocker.err
```

停止:

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh stop
```

再開:

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh start
```

Mac 側の `config.json` 例:

```json
{
  "api_base_url": "https://example.execute-api.ap-northeast-1.amazonaws.com",
  "check_path": "/v1/check",
  "user_id": "child-001",
  "device_id": "macbook-001",
  "token_path": "/Library/Application Support/DeviceLocker/device.token",
  "state_path": "/var/db/devicelocker/state.json",
  "lock_command": "/usr/local/sbin/devicelocker-lock",
  "notification_command": "/usr/local/sbin/devicelocker-notify",
  "notification_title": "DeviceLocker",
  "notification_threshold_seconds": [300, 180, 60],
  "grace_period_seconds": 60,
  "timeout_seconds": 5,
  "max_usage_delta_seconds": 120,
  "check_interval_seconds": 60,
  "exhausted_check_interval_seconds": 10
}
```

## MVP の秘密情報管理

MVP では `DeviceLockerDevices.DeviceToken` に HMAC 検証用の共有秘密を保存する。これは実装を単純にするための暫定方式。

次フェーズでは Secrets Manager または KMS 暗号化属性に移す。

## 判定

Lambda は以下を検証する。

- 登録済み `deviceId`
- `userId` と `deviceId` の紐づき
- timestamp の許容範囲
- `usageDeltaSeconds` の上限
- HMAC-SHA256 signature
- nonce の再利用

検証後、`usageDeltaSeconds` を `RemainingSeconds` から減らし、残り時間があれば `allow`、ゼロなら `deny` を返す。

## 実機確認

2026-06-12 に Mac 側設定後、以下の手動実行で AWS 連携を確認した。

```sh
sudo /usr/local/sbin/devicelocker-check
```

結果:

```text
allow: remaining_seconds=600
```

LaunchDaemon 起動後の確認:

```sh
sudo scripts/start-agent.sh
tail -f /var/log/devicelocker.err
```

結果:

```text
allow: remaining_seconds=480
allow: remaining_seconds=2239
```

`com.devicelocker.agent` が root LaunchDaemon として起動し、AWS から `allow` を取得できることを確認済み。

手動停止と復帰の確認:

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh stop
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh start
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh +30
```

エージェントログ:

```text
locking via /usr/local/sbin/devicelocker-lock
allow: remaining_seconds=3796
```

`stop` 後に LaunchDaemon が deny を受け取り、ロックコマンドを実行できることを確認済み。`start` と `+30` 後は AWS 側が `IsApproved=true`, `RemainingSeconds=3796` に戻ることを確認済み。

自然ゼロ到達の確認:

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh set-seconds 60
tail -n 0 -f /var/log/devicelocker.err
```

エージェントログ:

```text
2026-06-12T21:29:58+0900 allow: remaining_seconds=1675
2026-06-12T21:30:58+0900 locking via /usr/local/sbin/devicelocker-lock
```

AWS 側で `RemainingSeconds=0` になった後、次回チェックで LaunchDaemon がロックコマンドを実行できることを確認済み。確認後は `+30` で `RemainingSeconds=1800` に戻した。
