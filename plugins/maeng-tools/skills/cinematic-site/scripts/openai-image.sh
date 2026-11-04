#!/usr/bin/env bash
# Make one image with the OpenAI Images API. With references it calls the edits endpoint, otherwise generations.
# Every call spends API credit, so nothing here retries: a failure exits non-zero with the API's message
# and leaves any image already at OUT.png in place, since that one was paid for too.
set -euo pipefail

usage() { echo "usage: openai-image.sh PROMPT_FILE OUT.png WIDTHxHEIGHT low|medium|high [REF ...]" >&2; exit 2; }
[ $# -ge 4 ] || usage
prompt=$1 out=$2 size=$3 quality=$4; shift 4
[ -s "$prompt" ] || { echo "empty or missing prompt file: $prompt" >&2; exit 1; }
# checked before the call: the response is lost if it cannot be saved
[ -d "$(dirname "$out")" ] || { echo "no such folder for: $out" >&2; exit 1; }

model=gpt-image-2
base=${OPENAI_IMAGE_BASE_URL:-https://api.openai.com/v1} # the override exists for the test's fake server
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

if [ $# -gt 0 ]; then
  url=$base/images/edits
  args=(--form-string "model=$model" --form-string "size=$size" --form-string "quality=$quality" -F "prompt=<\"$prompt\"")
  for ref in "$@"; do args+=(-F "image[]=@\"$ref\""); done
else
  url=$base/images/generations
  jq -n --rawfile prompt "$prompt" --arg model "$model" --arg size "$size" --arg quality "$quality" \
    '{model: $model, prompt: $prompt, size: $size, quality: $quality}' > "$work/request.json"
  args=(-H 'Content-Type: application/json' --data-binary "@$work/request.json")
fi

key=$(security find-generic-password -s openai-api-key -w)
# printf is a builtin and curl reads the header from stdin, so the key never reaches any argv.
# -q must stay first: it skips ~/.curlrc, where --retry would spend credit and --verbose would print the key.
status=$(printf 'header = "Authorization: Bearer %s"\n' "$key" |
  curl -q -sS -K - --max-time 600 -o "$work/response.json" -w '%{http_code}' "${args[@]}" "$url")

if [ "$status" != 200 ]; then
  echo "openai-image: HTTP $status: $(jq -r '.error.message // .' "$work/response.json" 2>/dev/null || cat "$work/response.json")" >&2
  exit 1
fi
jq -er '.data[0].b64_json' "$work/response.json" | base64 --decode > "$work/image"
[ -s "$work/image" ] || { echo "openai-image: the response held an empty image" >&2; exit 1; }
mv "$work/image" "$out"
echo "$out"
