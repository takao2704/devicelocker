# ローカルモック実行

AWS 側を作る前に、ローカルのモック API で Mac エージェントを一周させる。

## 起動

別ターミナルでモック API を起動する。

```sh
python3 mock/mock_check_api.py
```

初期状態は `tmp/mock-api-state.json` に保存される。

## エージェントを 1 回実行

実ロックしないロックスタブを使って、`devicelocker-check` を 1 回実行する。

```sh
scripts/run-local-agent-check.sh
```

ローカル状態は `tmp/local-agent/state.json` に保存される。

ロック要求は `tmp/local-agent/lock.log` に記録される。

## 時間追加

```sh
python3 mock/mock_credit.py +30
python3 mock/mock_credit.py status
```

## 停止

```sh
python3 mock/mock_credit.py stop
scripts/run-local-agent-check.sh
```

`stop` 後にエージェントを実行すると、ロックスタブが呼ばれて `lock.log` に記録される。

## 再開

```sh
python3 mock/mock_credit.py start
python3 mock/mock_credit.py +10
scripts/run-local-agent-check.sh
```
