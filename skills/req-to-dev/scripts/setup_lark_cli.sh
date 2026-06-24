#!/usr/bin/env bash
# 使用项目内 secrets.local.json 初始化 lark-cli（凭证在 config/lark-cli-home/，已 gitignore）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
CONFIG_DIR="$ROOT/skills/req-to-dev/config"
SECRETS="$CONFIG_DIR/secrets.local.json"
LIB="$ROOT/skills/req-to-dev/scripts/lib"

if ! command -v lark-cli >/dev/null 2>&1; then
  echo "安装 @larksuite/cli ..."
  npm install -g @larksuite/cli@latest
fi

if [[ ! -f "$SECRETS" ]]; then
  echo "ERROR: 未找到 $SECRETS"
  echo "请执行: cp $CONFIG_DIR/secrets.local.json.example $SECRETS"
  echo "并填写 feishu.app_id / feishu.app_secret"
  exit 1
fi

eval "$(python3 -c "
import sys
sys.path.insert(0, '$LIB')
from local_config import ensure_lark_cli_config, lark_cli_profile, resolve_feishu_credentials, LARK_CLI_HOME
ensure_lark_cli_config()
app_id, _ = resolve_feishu_credentials()
print('export LARK_CLI_HOME_DIR=' + repr(str(LARK_CLI_HOME.resolve())))
print('export LARK_PROFILE=' + repr(lark_cli_profile()))
print('export LARK_APP_ID=' + repr(app_id))
")"

echo "配置 lark-cli profile=$LARK_PROFILE app_id=$LARK_APP_ID"
echo "  项目内 HOME: $LARK_CLI_HOME_DIR"
echo "  配置文件: $LARK_CLI_HOME_DIR/.lark-cli/config.json"

echo ""
echo "验证 fetch ..."
HOME="$LARK_CLI_HOME_DIR" lark-cli docs +fetch \
  --doc "https://beike.feishu.cn/wiki/CKFdwt35oitbqPkU690cVMnln3g" \
  --doc-format markdown --format pretty | head -5

echo ""
echo "✓ lark-cli 就绪: $(command -v lark-cli)"
