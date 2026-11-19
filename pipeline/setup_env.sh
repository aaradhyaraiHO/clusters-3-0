#!/usr/bin/env bash
# Create the pipeline environment and download the multilingual embedding model.
# Usage: ./setup_env.sh [target_dir]   (default: .env-clusters next to this script)
# The model is fetched with curl: huggingface_hub's own downloader fails behind some proxies (TLS OSStatus error).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
target="${1:-$here/.env-clusters}"
model="$target/models/paraphrase-multilingual-MiniLM-L12-v2"

uv venv -p 3.12 "$target/venv"
VIRTUAL_ENV="$target/venv" uv pip install -r "$here/requirements.txt"

mkdir -p "$model/1_Pooling"
base=https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/resolve/main
for f in config.json modules.json sentence_bert_config.json tokenizer.json tokenizer_config.json \
         special_tokens_map.json config_sentence_transformers.json 1_Pooling/config.json model.safetensors; do
  curl -sSfL -o "$model/$f" "$base/$f"
done
echo "python: $target/venv/bin/python"
echo "model:  $model"
