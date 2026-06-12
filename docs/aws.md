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
  "grace_period_seconds": 60,
  "timeout_seconds": 5,
  "max_usage_delta_seconds": 120
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
