#!/bin/bash
# 启动公开演示网页（FastAPI 同源，复用 main_graph / batch_main_graph）
# 用法：bash scripts/run_demo_web.sh [-p 端口]
set -e

PORT="${DEPLOY_RUN_PORT:-5000}"
WORK_DIR="${COZE_WORKSPACE_PATH:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

while getopts "p:h" opt; do
  case "$opt" in
    p) PORT="$OPTARG";;
    h) echo "用法: $0 [-p 端口]"; exit 0;;
  esac
done

# 若存在 .venv 则激活
if [ -f "${WORK_DIR}/.venv/bin/activate" ]; then
  source "${WORK_DIR}/.venv/bin/activate"
fi

cd "${WORK_DIR}"
echo "启动公开演示页 http://0.0.0.0:${PORT}/ （根路径 /）"
PYTHONPATH="${WORK_DIR}/src" exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT}"