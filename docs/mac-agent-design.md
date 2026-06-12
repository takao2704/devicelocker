# Mac エージェント設計

## 配置

| 種別 | パス | 所有者 | 権限 |
| --- | --- | --- | --- |
| LaunchDaemon | `/Library/LaunchDaemons/com.devicelocker.agent.plist` | `root:wheel` | `644` |
| 実行ファイル | `/usr/local/sbin/devicelocker-check` | `root:wheel` | `750` |
| 設定ディレクトリ | `/Library/Application Support/DeviceLocker` | `root:wheel` | `750` |
| 状態ディレクトリ | `/var/db/devicelocker` | `root:wheel` | `750` |
| 状態ファイル | `/var/db/devicelocker/state.json` | `root:wheel` | `600` |

## LaunchDaemon

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.devicelocker.agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/sbin/devicelocker-check</string>
  </array>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/var/log/devicelocker.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/devicelocker.err</string>
</dict>
</plist>
```

## インストール

エージェント本体と LaunchDaemon plist は以下で配置する。

```sh
sudo scripts/install-agent.sh
```

インストール後、起動前に以下を作成する。

```text
/Library/Application Support/DeviceLocker/config.json
/Library/Application Support/DeviceLocker/device.token
```

`config/config.example.json` を設定ファイルの雛形として使う。

AWS デプロイ後は、表示された API endpoint と device token を使って以下で設定できる。

```sh
sudo API_BASE_URL="https://example.execute-api.ap-northeast-1.amazonaws.com" \
  DEVICE_TOKEN="表示された device token" \
  scripts/install-device-config.sh
```

LaunchDaemon の読み込み:

```sh
sudo scripts/start-agent.sh
```

停止:

```sh
sudo scripts/stop-agent.sh
```

削除:

```sh
sudo scripts/uninstall-agent.sh
```

## 状態遷移

```text
start
  |
  v
load config/token/state
  |
  v
call CheckMacStatus
  |
  +-- success + allow --> update remaining time/state --> exit
  |
  +-- success + deny  --> update state --> lock --> exit
  |
  +-- failure --------> within grace? -- yes --> exit
                         |
                         no
                         v
                       lock --> exit
```

## 通信失敗時の扱い

- 前回成功時刻がない場合は、原則としてロックする。
- 前回成功時のローカル時刻 `last_success_local_at` から `grace_period_seconds` 以内ならロックしない。
- 猶予を超えた場合は deny と同等に扱う。
- ロック後も次回実行で API 確認を続ける。

## 利用時間の消費

- MVP では LaunchDaemon の実行間隔を利用し、前回成功から今回成功までの経過秒数を `usageDeltaSeconds` として API に報告する。
- サーバーは報告された `usageDeltaSeconds` を残り時間から減算する。
- `usageDeltaSeconds` は過大報告や異常値を防ぐため、サーバー側で 0 から 120 秒程度に丸める。
- 残り時間がゼロ以下になった場合、API は `deny` を返す。
- 画面ロック中やログアウト中の時間を消費対象に含めるかは後続で精密化する。MVP では実装と運用の簡単さを優先し、エージェントが定期実行できている時間を消費対象にする。

## ロック実行

ロックコマンドは実装前に対象 macOS で検証して固定する。

検証条件:

- コマンド実行後、画面復帰にパスワード入力が必要であること。
- root の LaunchDaemon から実行できること。
- アクティブな GUI セッションに対して効くこと。
- 実行に過度な副作用がないこと。

現在の候補:

```text
/usr/local/sbin/devicelocker-lock
```

この候補は root 所有の薄いラッパーとして `/usr/bin/pmset displaysleepnow` を実行する。対象ユーザーの screenLock delay を immediate にするセットアップ手順と組み合わせて検証する。`pmset displaysleepnow` 単体では即時ロックを保証しない。

root LaunchDaemon 経由の検証には、一時的に `launchd/com.devicelocker.locktest.plist` を使った。検証結果として、root LaunchDaemon から `/usr/local/sbin/devicelocker-lock` を実行し、復帰時に子どもアカウントのパスワード入力が必要になることを確認済み。

セットアップ候補:

```text
/usr/sbin/sysadminctl -screenLock immediate -password -
```

この候補は対象ユーザーごとの一回限りの設定として扱う。DeviceLocker の通常実行時にはパスワードを扱わない。

旧候補:

```text
/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession -suspend
```

この旧候補は macOS 14.8.7 ではパスが存在しなかったため採用しない。

## エラー処理

- 設定ファイルが読めない場合はロックする。
- デバイストークンが読めない場合はロックする。
- 状態ファイルが壊れている場合は新規状態として扱い、通信できなければロックする。
- API が 4xx を返した場合は原則 deny と同等に扱う。
- API が 5xx またはタイムアウトした場合は通信失敗として猶予判定する。

## ログ

`/var/log/devicelocker.err` に時刻付きで判定結果を出力する。

例:

```text
2026-06-12T21:30:00+0900 allow: remaining_seconds=1800
2026-06-12T21:31:00+0900 locking via /usr/local/sbin/devicelocker-lock
```
