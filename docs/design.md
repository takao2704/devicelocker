# DeviceLocker 基本設計

## 目的

子ども用 MacBook の利用可否を AWS 側の許可状態で判定し、未承認・許可期限切れ・通信失敗時の猶予超過では Mac をロックする。

初期版は「指定時刻まで利用を許可する」モデルに限定する。日次利用時間の積算、複数ユーザー管理、Web UI は後続フェーズとして扱う。

## 対象範囲

### MVP に含める

- Mac 側エージェントの定期実行
- AWS 側の状態確認 API
- DynamoDB によるユーザー別許可状態管理
- 通信失敗時の 5 分猶予とフェイルセーフロック
- HMAC 署名による簡易デバイス認証
- 保護者向け LINE Bot による許可時間更新

### MVP から外す

- 日次の実利用時間積算
- 複数 Mac / 複数ユーザーの高度な管理 UI
- 管理者権限を持つ利用者への完全な耐性
- MDM を前提にした端末制御

## 全体構成

```text
[Child MacBook]
  LaunchDaemon
    - 60 秒ごとにチェック処理を起動
    - API 判定結果を state.json に保存
    - deny または猶予超過でロックを実行

        |
        | HTTPS + HMAC signature
        v

[API Gateway]
        |
        v
[Lambda: CheckMacStatus]
        |
        v
[DynamoDB: DeviceLockerControl]

[LINE Bot]
        |
        v
[Lambda: UpdateAllowance]
        |
        v
[DynamoDB: DeviceLockerControl]
```

## コンポーネント責務

### Mac エージェント

- root 所有の LaunchDaemon から 60 秒ごとに起動する。
- API に `userId`, `deviceId`, `timestamp`, `nonce`, `signature` を送る。
- API 応答が `allow` の場合はローカル状態を更新して終了する。
- API 応答が `deny` の場合はローカル状態を更新してロックする。
- 通信失敗時は前回成功時刻から 5 分以内なら何もしない。
- 通信失敗が 5 分を超えた場合は deny と同等に扱いロックする。
- ローカル時刻だけで許可判定をしない。API 応答の `serverTime` を基準に状態を更新する。

### AWS API

- API Gateway 経由で Lambda を呼び出す。
- Lambda は HMAC 署名、timestamp、nonce を検証する。
- DynamoDB から対象ユーザーまたは端末の許可状態を取得する。
- `IsApproved` と `AllowUntil` をもとに `allow` / `deny` を返す。
- 応答にはサーバー時刻と判定理由を含める。

### 保護者インターフェース

- 初期版は LINE Bot を採用する。
- `30`, `60`, `stop` のような短いコマンドで許可状態を更新する。
- LINE Bot 用 Lambda は、将来 Web UI からも再利用できる更新処理を呼び出す。

## セキュリティ方針

- 子ども用アカウントは標準ユーザーに固定する。
- LaunchDaemon、スクリプト、設定、デバイストークンは root 所有にする。
- デバイストークンは標準ユーザーから読めない権限で保存する。
- HMAC 署名で API のなりすましと単純な再送を抑止する。
- 家庭内運用では端末内秘密情報を完全には守れない前提で、実用上の回避難度を上げる。

## 主な設計判断

| 項目 | 判断 |
| --- | --- |
| 実行方式 | LaunchDaemon による短時間実行 |
| 判定間隔 | 60 秒 |
| オフライン猶予 | 初期値 5 分 |
| 許可モデル | `AllowUntil` による期限付き許可 |
| API 認証 | device token + HMAC |
| 保護者 UI | 初期版は LINE Bot |
| ロック方式 | 対象 macOS で実機検証した方式のみ採用 |

## 未決事項

- 対象 Mac の macOS バージョン。
- 最終的に採用するロックコマンド。
- LINE Bot の親ユーザー認証方法。
- `userId` と `deviceId` の関係を 1:1 に固定するか。
- nonce の保存期間と保存先。
- DynamoDB テーブルを 1 テーブル構成にするか、デバイス情報を分離するか。
