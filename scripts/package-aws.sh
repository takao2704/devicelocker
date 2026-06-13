#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="$ROOT/tmp/aws-build"
ZIP_PATH="$ROOT/tmp/check_mac_status.zip"

rm -rf "$BUILD_DIR" "$ZIP_PATH"
mkdir -p "$BUILD_DIR"
cp "$ROOT/aws/check_mac_status/app.py" "$BUILD_DIR/app.py"

python3 - "$ROOT" "$BUILD_DIR" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
build_dir = Path(sys.argv[2])
ui_dir = root / "prototypes" / "parent-time-ui"

html = (ui_dir / "index.html").read_text(encoding="utf-8")
styles = (ui_dir / "src" / "styles.css").read_text(encoding="utf-8")
lucide = (ui_dir / "src" / "lucide.min.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
app = (ui_dir / "src" / "app.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
config = """
window.DEVICELOCKER_CONFIG = {
  apiBaseUrl: window.location.origin,
  cognitoDomain: "__PARENT_COGNITO_DOMAIN__",
  cognitoClientId: "__PARENT_USER_POOL_CLIENT_ID__",
  redirectUri: "__PARENT_REDIRECT_URI__",
  logoutUri: "__PARENT_LOGOUT_URI__",
  userId: "child-001",
  identityProvider: "Google",
};
""".strip().replace("</script", "<\\/script")

html = html.replace('    <link rel="stylesheet" href="./src/styles.css?v=20260613-usage-history" />', f"    <style>\n{styles}\n    </style>")
html = html.replace('    <script src="./src/lucide.min.js"></script>', f"    <script>\n{lucide}\n    </script>")
html = html.replace('    <script src="./src/config.js"></script>', f"    <script>\n{config}\n    </script>")
html = html.replace('    <script src="./src/app.js?v=20260613-usage-history"></script>', f"    <script>\n{app}\n    </script>")

(build_dir / "parent_ui.html").write_text(html, encoding="utf-8")
PY

(cd "$BUILD_DIR" && zip -q "$ZIP_PATH" app.py parent_ui.html)

echo "$ZIP_PATH"
