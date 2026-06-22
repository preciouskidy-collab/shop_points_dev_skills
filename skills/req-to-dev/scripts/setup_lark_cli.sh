#!/usr/bin/env bash
# 使用与 feishu_fetcher 相同的飞书应用凭证初始化 lark-cli
set -euo pipefail

FEISHU_CONFIG="${HOME}/.shop-points-dev-skills/feishu-config.json"
PROFILE_NAME="${LARK_CLI_PROFILE:-shop-points-dev}"

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "安装 @larksuite/cli ..."
  npm install -g @larksuite/cli@latest
fi

if [[ ! -f "$FEISHU_CONFIG" ]]; then
  echo "ERROR: 未找到 $FEISHU_CONFIG"
  echo "请先运行 feishu_fetcher 并配置 app_id / app_secret"
  exit 1
fi

APP_ID=$(python3 -c "import json; print(json.load(open('$FEISHU_CONFIG'))['app_id'])")
APP_SECRET=$(python3 -c "import json; print(json.load(open('$FEISHU_CONFIG'))['app_secret'])")

echo "配置 lark-cli profile=$PROFILE_NAME app_id=$APP_ID"
echo "$APP_SECRET" | lark-cli config init \
  --app-id "$APP_ID" \
  --app-secret-stdin \
  --brand feishu \
  --name "$PROFILE_NAME"

echo ""
echo "验证 fetch ..."
lark-cli docs +fetch --doc "https://beike.feishu.cn/wiki/CKFdwt35oitbqPkU690cVMnln3g" \
  --doc-format markdown --format pretty | head -5

echo ""
echo "✓ lark-cli 就绪: $(command -v lark-cli)"
