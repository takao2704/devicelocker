# 実装計画

## Phase 1: AWS 判定 API

1. DynamoDB テーブルを定義する。完了。
2. `CheckMacStatus` Lambda を実装する。完了。
3. HMAC 署名付きで `remainingSeconds` による `allow` / `deny` 判定を確認する。ローカルテスト完了。
4. API Gateway から Lambda を呼び出せるようにする。CloudFormation 定義完了。
5. テストデータで `RemainingSeconds` と `IsApproved` の判定を確認する。ローカルテスト完了。

完了条件:

- `IsApproved=false` で `deny` が返る。
- `RemainingSeconds=0` なら `deny` が返る。
- `RemainingSeconds>0` なら `allow` が返る。
- `usageDeltaSeconds` に応じて `RemainingSeconds` が減る。

実装:

- `aws/check_mac_status/app.py`
- `aws/template.json`
- `scripts/deploy-aws.sh`
- `scripts/seed-aws-device.sh`
- `scripts/update-aws-credit.sh`
- `tests/test_check_mac_status_lambda.py`

## Phase 2: Mac エージェント試作

1. 設定ファイル、トークン、状態ファイルの読み書きを実装する。完了。
2. API 呼び出し処理を実装する。完了。
3. `allow` で残り時間と状態を更新して終了する。完了。
4. `deny` でロック関数を呼ぶ。完了。
5. 通信失敗時の 1 分猶予を実装する。完了。

完了条件:

- API の応答に応じて状態ファイルが更新される。
- 通信失敗が 1 分の猶予内ならロックしない。
- 通信失敗が猶予超過ならロック関数が呼ばれる。
- root LaunchDaemon として起動し、AWS から `allow` を取得できる。完了。
- AWS 側の `stop` 操作後に root LaunchDaemon がロックコマンドを実行できる。完了。
- AWS 側の `RemainingSeconds=0` 到達後に root LaunchDaemon がロックコマンドを実行できる。完了。

実装:

- `bin/devicelocker-check`
- `launchd/com.devicelocker.agent.plist`
- `scripts/install-agent.sh`
- `scripts/start-agent.sh`
- `scripts/stop-agent.sh`
- `scripts/uninstall-agent.sh`
- `tests/test_devicelocker_check.py`

## Phase 3: ロック方式検証

1. 対象 Mac の macOS バージョンを記録する。
2. 候補コマンドを手動実行してロック成立を確認する。
3. LaunchDaemon 経由で同じコマンドが効くことを確認する。
4. 採用コマンドを設定として固定する。

完了条件:

- 実行後にパスワード入力が必要になる。
- root LaunchDaemon から実行しても同じ結果になる。

## Phase 4: HMAC 署名

1. デバイストークンを発行する。
2. Mac 側で署名生成を実装する。
3. Lambda 側で署名検証を実装する。
4. timestamp 許容範囲を設定する。
5. nonce の重複検出を実装する。

完了条件:

- 正しい署名だけ API が受理する。
- 古い timestamp が拒否される。
- 同じ nonce の再利用が拒否される。

## Phase 5: 手動時間追加

1. 親が手動で時間追加できる CLI または簡易 Lambda 呼び出しを作る。AWS CLI 版は完了。
2. `+30`, `+60`, `set-seconds`, `stop` コマンドを実装する。AWS CLI 版は完了。
3. DynamoDB 更新処理を `AddUsageCredit` として分離する。
4. 必要になったら LINE webhook Lambda を追加する。

完了条件:

- 親が手動で残り利用可能時間を追加できる。
- 更新後に Mac 側 API の判定が変わる。

## 直近で決めること

- AWS IaC は CDK / SAM / Terraform のどれにするか。
- Lambda 実装言語を Python / TypeScript のどちらにするか。
- Mac エージェントを shell / Python / Swift のどれで実装するか。
- LINE Bot を後続に回し、MVP は CLI 更新で代替する。
