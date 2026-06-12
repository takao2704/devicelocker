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

通常ユーザーでの実行結果:

```text
$ scripts/lock-spike.sh lock-now
2026-06-12 20:16:10.239 sysadminctl[33772:277674] Password is required!
```

sudo 実行結果:

```text
$ sudo scripts/lock-spike.sh lock-now
2026-06-12 20:17:43.167 sysadminctl[37129:283204] Password is required!
```

delay に `0` を指定した結果:

```text
$ scripts/lock-spike.sh set-delay-zero
Enter password for Takao Ide :
2026-06-12 20:19:59.452 sysadminctl[42871:292343] Unknown state for screenLock (0)
```

delay に `immediate` を指定した後の status:

```text
$ scripts/lock-spike.sh status
2026-06-12 20:21:23.188 sysadminctl[47579:299483] screenLock delay is immediate
```

`pmset displaysleepnow` の実行:

```text
$ scripts/lock-spike.sh display-sleep-now
```

CLI 上はエラーなく終了し、画面復帰時にパスワード入力が必要だった。

結論:

- `sysadminctl -screenLock immediate` は、ロック実行コマンドではなく screenLock delay を immediate に設定する操作として扱う。
- `0` 秒指定は受け付けない。
- `immediate` 指定により screenLock delay が immediate になることを確認済み。
- screenLock delay が immediate の状態で `pmset displaysleepnow` を実行すると、復帰時にパスワード入力が必要になることを確認済み。
- `sysadminctl -help` 上は `-screenLock <status || immediate || off || seconds> -password <password>`。
- DeviceLocker の通常実行時にはパスワードを扱わず、セットアップ時だけ `immediate` 設定を行う。

## 採用候補

MVP では、セットアップ時に screenLock delay を短くしたうえで、実行時に以下を呼ぶ案を次候補にする。

セットアップ時:

```text
/usr/sbin/sysadminctl -screenLock immediate -password -
```

このコマンドは親がパスワードを入力する一回限りの設定として扱う。DeviceLocker の通常実行時にはパスワードを扱わない。

ロック実行時:

```text
/usr/bin/pmset displaysleepnow
```

この方式は `pmset displaysleepnow` 単体ではなく、事前設定と組み合わせて検証する。

1. セットアップ時に screenLock delay を immediate にする。
2. `pmset displaysleepnow` 実行後、復帰時にパスワード入力が必要か確認する。
3. root LaunchDaemon から `pmset displaysleepnow` を実行して、GUI セッションに対して効くか確認する。

効かない場合は、次の順で代替を検証する。

1. `launchctl asuser <console_uid>` 経由でユーザーセッション内からロック相当の操作を実行する。
2. 構成プロファイルで screenLock delay を強制する。
3. MDM を使う。

## 受け入れ条件

- `0` 秒指定は `Unknown state for screenLock (0)` になることを確認済み。
- セットアップ時に screenLock delay を immediate に設定できることを確認済み。
- ユーザーセッションから `pmset displaysleepnow` を実行した場合、復帰時にパスワード入力が必要になることを確認済み。
- 採用候補コマンドを root LaunchDaemon から実行して画面がロックされる。
- 復帰時にパスワード入力が必要になる。
- 子ども用標準ユーザーから停止・変更できない。
- ロック後も LaunchDaemon の次回実行が継続される。

## 次の検証

1. root LaunchDaemon から同じコマンドを実行して、GUI セッションに対して効くか確認する。
