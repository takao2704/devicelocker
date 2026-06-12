#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BUILD_DIR="$ROOT/tmp/aws-build"
ZIP_PATH="$ROOT/tmp/check_mac_status.zip"

rm -rf "$BUILD_DIR" "$ZIP_PATH"
mkdir -p "$BUILD_DIR"
cp "$ROOT/aws/check_mac_status/app.py" "$BUILD_DIR/app.py"

(cd "$BUILD_DIR" && zip -q "$ZIP_PATH" app.py)

echo "$ZIP_PATH"
