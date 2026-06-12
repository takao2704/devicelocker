# Parent Time UI Prototype

Static mobile web prototype for the parent-facing DeviceLocker time-add flow.

Run locally from this directory:

```sh
python3 -m http.server 4173 --bind 127.0.0.1
```

Then open:

```text
http://127.0.0.1:4173/
```

The prototype stores edits in `localStorage` so reward-rule changes persist in the browser profile used for preview.

## Remote mode

`src/config.js` が以下の値を持つと、Cognito Hosted UI でログインして Parent Web API を呼び出す。

```js
window.DEVICELOCKER_CONFIG = {
  apiBaseUrl: "https://example.execute-api.ap-northeast-1.amazonaws.com",
  cognitoDomain: "https://example.auth.ap-northeast-1.amazoncognito.com",
  cognitoClientId: "Cognito app client ID",
  redirectUri: "http://127.0.0.1:4173/",
  logoutUri: "http://127.0.0.1:4173/",
  userId: "child-001",
  identityProvider: "Google",
};
```

空文字のままならローカルモードで動作する。

Amplify Hosting ではリポジトリ直下の `amplify.yml` が環境変数から `src/config.js` を生成する。
