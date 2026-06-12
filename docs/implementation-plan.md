# 実装計画

## Phase 1: AWS 判定 API

1. DynamoDB テーブルを定義する。
2. `CheckMacStatus` Lambda を実装する。
3. 署名なしで `allow` / `deny` 判定を確認する。
4. API Gateway から Lambda を呼び出せるようにする。
5. テストデータで `AllowUntil` と `IsApproved` の判定を確認する。

完了条件:

- `IsApproved=false` で `deny` が返る。
- `AllowUntil` が過去なら `deny` が返る。
- `AllowUntil` が未来なら `allow` が返る。

## Phase 2: Mac エージェント試作

1. 設定ファイル、トークン、状態ファイルの読み書きを実装する。
2. API 呼び出し処理を実装する。
3. `allow` で状態更新して終了する。
4. `deny` でロック関数を呼ぶ。
5. 通信失敗時の 5 分猶予を実装する。

完了条件:

- API の応答に応じて状態ファイルが更新される。
- 通信失敗が猶予内ならロックしない。
- 通信失敗が猶予超過ならロック関数が呼ばれる。

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

## Phase 5: LINE Bot

1. LINE webhook Lambda を作る。
2. 親 LINE ユーザー ID の allowlist を設定する。
3. `30`, `60`, `stop` コマンドを実装する。
4. DynamoDB 更新処理を `UpdateAllowance` として分離する。

完了条件:

- LINE から許可時間を更新できる。
- 未許可ユーザーからの操作は拒否される。
- 更新後に Mac 側 API の判定が変わる。

## 直近で決めること

- AWS IaC は CDK / SAM / Terraform のどれにするか。
- Lambda 実装言語を Python / TypeScript のどちらにするか。
- Mac エージェントを shell / Python / Swift のどれで実装するか。
- LINE Bot を MVP に同時投入するか、まずは CLI 更新で代替するか。
