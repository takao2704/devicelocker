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

結論:

- 通常ユーザー実行ではパスワード要求で止まる。
- DeviceLocker は root LaunchDaemon から実行するため、次の確認は root 実行時にパスワードなしで即時ロックできるかを見る。

## 採用候補

MVP では以下を root LaunchDaemon から実行する第一候補にする。

```text
/usr/sbin/sysadminctl -screenLock immediate
```

root LaunchDaemon から実行して効かない場合は、次の順で代替を検証する。

1. `launchctl asuser <console_uid>` 経由で `sysadminctl -screenLock immediate`
2. `pmset displaysleepnow` と screenLock delay の強制設定
3. MDM または構成プロファイル

## 受け入れ条件

- 通常ユーザー実行ではパスワード要求になることを確認済み。
- root LaunchDaemon から実行しても画面が即時ロックされる。
- 復帰時にパスワード入力が必要になる。
- 子ども用標準ユーザーから停止・変更できない。
- ロック後も LaunchDaemon の次回実行が継続される。

## 次の検証

1. `sudo scripts/lock-spike.sh lock-now` で root 実行時にパスワードなしでロックできるか確認する。
2. 復帰時にパスワード入力が必要か確認する。
3. root LaunchDaemon から同じコマンドを実行して、GUI セッションに対して効くか確認する。
