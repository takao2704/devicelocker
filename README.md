# DeviceLocker

DeviceLocker は、子ども用 Mac の利用可能時間を AWS 側で管理し、残り時間ゼロまたは親の停止操作で Mac をロックする MVP。

対象ユーザーは管理者権限を持たない子どもアカウント。親は AWS CLI で時間を追加・停止・再開する。

## 現在できること

- Mac が 60 秒ごとに AWS の `POST /v1/check` を確認する。
- AWS 側の `RemainingSeconds` が利用時間に応じて減る。
- `RemainingSeconds=0` で Mac がロックされる。
- `monitored_user_name` に設定した子どもアカウントが前面のときだけ利用時間を消費し、ロック対象にする。
- `stop` 操作で Mac がロックされる。
- `start` と `+30` で利用を再開できる。
- オフラインまたは API 失敗時は 1 分の猶予後にロックする。

## 構成

```text
Mac LaunchDaemon
  /usr/local/sbin/devicelocker-check
  /usr/local/sbin/devicelocker-lock

AWS
  API Gateway HTTP API: POST /v1/check
  Lambda: DeviceLockerCheckMacStatus
  DynamoDB: DeviceLockerControl
  DynamoDB: DeviceLockerDevices
  DynamoDB: DeviceLockerNonce
```

## 前提

- macOS 14.8.7 で検証済み。
- 子どもアカウントは標準ユーザーにする。
- AWS CLI を設定済みであること。
- Mac 側の対象ユーザーごとに screen lock delay を immediate にする。

## AWS セットアップ

```sh
AWS_REGION=ap-northeast-1 scripts/deploy-aws.sh
```

初期データを投入する。

```sh
DEVICE_TOKEN="$(openssl rand -base64 32)" \
REMAINING_SECONDS=600 \
AWS_REGION=ap-northeast-1 \
scripts/seed-aws-device.sh
```

表示された `DEVICE_TOKEN` は秘密情報。チャットや Git に貼らない。

## Mac セットアップ

### 親の管理者アカウントで実行

ロックコマンドをインストールする。

```sh
sudo scripts/install-lock-command.sh
```

### 子どもアカウントで実行

子どもアカウントで一度だけ screen lock delay を immediate にする。

```sh
/usr/local/sbin/devicelocker-lock-spike set-delay-immediate
```

このコマンドは子どもアカウントのパスワード入力を求める。復帰時にパスワードが必要になる設定なので、対象の子どもアカウントで実行する。

### 親の管理者アカウントで実行

AWS の CloudFormation output `ApiEndpoint` と、seed 時に表示された device token を使って設定する。

```sh
sudo API_BASE_URL="https://xxxxx.execute-api.ap-northeast-1.amazonaws.com" \
  DEVICE_TOKEN="表示された device token" \
  scripts/install-device-config.sh
```

既存の設定に対象ユーザーだけ追加・変更する場合:

```sh
sudo scripts/set-monitored-user.sh yuuto
```

エージェントをインストールする。

```sh
sudo scripts/install-agent.sh
```

手動で 1 回確認する。

```sh
sudo /usr/local/sbin/devicelocker-check
```

`allow: remaining_seconds=...` が出れば AWS 連携成功。

## 起動と停止

LaunchDaemon を起動する。

```sh
sudo scripts/start-agent.sh
```

ログを見る。

```sh
tail -n 0 -f /var/log/devicelocker.err
```

停止する。

```sh
sudo scripts/stop-agent.sh
```

削除する。

```sh
sudo scripts/uninstall-agent.sh
```

## 親の操作

残り時間を 30 分追加する。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh +30
```

利用を止める。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh stop
```

利用を再開する。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh start
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh +30
```

現在値を見る。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh status
```

試験用に残り秒数を直接セットする。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh set-seconds 60
```

## 安全に戻す

ロック試験後に安全側へ戻す。

```sh
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh start
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh +30
AWS_REGION=ap-northeast-1 scripts/update-aws-credit.sh status
```

エージェントを止める場合:

```sh
sudo scripts/stop-agent.sh
```

## ローカルモック

AWS を使わずにエージェントを一周させる。

```sh
python3 mock/mock_check_api.py
```

別ターミナルで:

```sh
scripts/run-local-agent-check.sh
python3 mock/mock_credit.py stop
scripts/run-local-agent-check.sh
python3 mock/mock_credit.py start
python3 mock/mock_credit.py +10
scripts/run-local-agent-check.sh
```

詳細は [docs/local-mock.md](docs/local-mock.md)。

## テスト

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile bin/devicelocker-check aws/check_mac_status/app.py mock/mock_check_api.py mock/mock_credit.py
python3 -m json.tool aws/template.json >/dev/null
```

## 検証済み

- root LaunchDaemon から AWS の `allow` を取得できる。
- AWS 側の `stop` 後に root LaunchDaemon が `/usr/local/sbin/devicelocker-lock` を実行できる。
- AWS 側の `RemainingSeconds=0` 到達後に root LaunchDaemon がロックできる。
- ロック後、`start` と時間追加で復帰できる。

詳細は [docs/aws.md](docs/aws.md) と [docs/lock-spike.md](docs/lock-spike.md)。

## 注意

MVP では `DeviceLockerDevices.DeviceToken` に HMAC 共有秘密を保存している。次フェーズでは Secrets Manager または KMS 暗号化属性に移す。
