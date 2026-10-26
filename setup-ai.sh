#!/bin/sh
# Install only local inference. No subscription, paid endpoint or API key.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
sipi_images=false
case "${1:-}" in "") ;; --images) sipi_images=true ;; *) echo 'Usage: ./setup-ai.sh [--images]' >&2; exit 1 ;; esac
if [ -f backend/.env ]; then set -a; . ./backend/.env; set +a; fi
mkdir -p .runtime
if command -v ollama >/dev/null 2>&1; then
  sipi_ollama=$(command -v ollama)
elif [ -x .runtime/ollama ]; then
  sipi_ollama="$PWD/.runtime/ollama"
elif [ -x .runtime/bin/ollama ]; then
  sipi_ollama="$PWD/.runtime/bin/ollama"
else
  case "$(uname -s):$(uname -m)" in
    Darwin:arm64|Darwin:x86_64) sipi_bundle=ollama-darwin.tgz ;;
    Linux:x86_64) sipi_bundle=ollama-linux-amd64.tar.zst ;;
    Linux:aarch64) sipi_bundle=ollama-linux-arm64.tar.zst ;;
    *) echo 'Установите Ollama с https://ollama.com/download, затем повторите команду.' >&2; exit 1 ;;
  esac
  echo 'Загружаем Ollama в .runtime — системные файлы не меняются.'
  curl -fL --retry 3 "https://github.com/ollama/ollama/releases/download/v0.40.8/$sipi_bundle" -o ".runtime/$sipi_bundle"
  case "$sipi_bundle" in
    *.tgz) tar -xzf ".runtime/$sipi_bundle" -C .runtime ;;
    *) tar --zstd -xf ".runtime/$sipi_bundle" -C .runtime ;;
  esac
  if [ -x .runtime/bin/ollama ]; then sipi_ollama="$PWD/.runtime/bin/ollama"; else sipi_ollama="$PWD/.runtime/ollama"; fi
fi
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
case "$OLLAMA_HOST" in
  http://*|https://*) sipi_ollama_url="$OLLAMA_HOST" ;;
  *) sipi_ollama_url="http://$OLLAMA_HOST" ;;
esac
export ASSISTANT_OLLAMA_URL="${ASSISTANT_OLLAMA_URL:-$sipi_ollama_url}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$PWD/.runtime/models}"
export OLLAMA_NO_CLOUD=1
sipi_ollama_pid=""
cleanup() { if [ -n "$sipi_ollama_pid" ]; then kill "$sipi_ollama_pid" 2>/dev/null || true; wait "$sipi_ollama_pid" 2>/dev/null || true; fi; }
trap cleanup EXIT INT TERM
if ! curl -fsS --max-time 2 "$ASSISTANT_OLLAMA_URL/api/tags" >/dev/null 2>&1; then
  "$sipi_ollama" serve > .runtime/ollama.log 2>&1 &
  sipi_ollama_pid=$!
  sipi_attempt=0
  until curl -fsS --max-time 2 "$ASSISTANT_OLLAMA_URL/api/tags" >/dev/null 2>&1; do
    sipi_attempt=$((sipi_attempt + 1))
    if [ "$sipi_attempt" -ge 30 ]; then echo 'Не удалось запустить Ollama. Подробности: .runtime/ollama.log' >&2; exit 1; fi
    sleep 1
  done
fi
"$sipi_ollama" pull "${ASSISTANT_MODEL:-qwen3:4b}"
if [ "$sipi_images" = true ]; then
  if [ ! -x backend/.venv/bin/python ]; then python3 -m venv backend/.venv; fi
  backend/.venv/bin/python -m pip install -r backend/requirements-ai.txt
  echo 'Загружаем SDXL-Turbo для учебной генерации концептов (~7 ГБ).'
  # Only weights/configuration required by the local fp16 pipeline; no remote Python code.
  backend/.venv/bin/python - "$PWD/.runtime/image-model" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download('stabilityai/sdxl-turbo', local_dir=sys.argv[1], allow_patterns=[
    'model_index.json', '*/config.json', '*/scheduler_config.json', '*/tokenizer_config.json',
    '*/special_tokens_map.json', '*/vocab.json', '*/merges.txt',
    '*/model.fp16.safetensors', '*/diffusion_pytorch_model.fp16.safetensors'])
PY
fi
echo 'Готово. Запустите ./start.sh. Модели работают локально, платежей за запросы нет.'
