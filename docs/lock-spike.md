# ロック方式スパイク

## 目的

対象 Mac で、DeviceLocker が残り時間ゼロまたはフェイルセーフ時に確実に画面ロックできる方式を確認する。

## 実機情報

確認日時: 2026-06-12

```text
ProductName: macOS
ProductVersion: 14.8.7
BuildVersion: 23J520
Architecture: arm64
```

## 確認結果

### CGSession

当初候補:

```text
/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession -suspend
```

この Mac では上記パスが存在しなかった。

結論:

- macOS 14.8.7 では採用しない。
- 古い macOS 向け候補としてのみ扱う。

### pmset displaysleepnow

コマンドは存在する。

```text
/usr/bin/pmset displaysleepnow
```

ただし `pmset displaysleepnow` はディスプレイをスリープさせるだけで、即時ロックは macOS の screenLock delay 設定に依存する。

この Mac の確認結果:

```text
screenLock delay is 300 seconds
```

結論:

- 即時ロック目的の第一候補にはしない。
- 画面スリープの補助としては使える可能性がある。

### sysadminctl screenLock

コマンドは存在する。

```text
/usr/sbin/sysadminctl -screenLock immediate
```

`sysadminctl -help` に `-screenLock <status || immediate || off || seconds>` が表示される。

結論:

- macOS 14.8.7 の第一候補にする。
- 次の確認は、手動実行と root LaunchDaemon 経由の両方で「復帰時にパスワード入力が必要になること」を見る。

## 採用候補

MVP では以下を第一候補にする。

```text
/usr/sbin/sysadminctl -screenLock immediate
```

root LaunchDaemon から実行して効かない場合は、次の順で代替を検証する。

1. `launchctl asuser <console_uid>` 経由で `sysadminctl -screenLock immediate`
2. `pmset displaysleepnow` と screenLock delay の強制設定
3. MDM または構成プロファイル

## 受け入れ条件

- 手動実行で画面が即時ロックされる。
- root LaunchDaemon から実行しても画面が即時ロックされる。
- 復帰時にパスワード入力が必要になる。
- 子ども用標準ユーザーから停止・変更できない。
- ロック後も LaunchDaemon の次回実行が継続される。

## 未完了

実際に画面をロックする実行テストは、作業セッションを中断するためまだ行っていない。
