#!/usr/bin/env bash
# Turn a generated clip into a seamless web background: forward + reversed copy,
# so a plain <video loop> never jumps back to frame 0. Writes NAME.mp4, NAME.webm, NAME.jpg.
# shortcut: ffmpeg's reverse filter holds the whole clip in memory (~1 GB for 10 s 1080p); trim longer clips first.
set -euo pipefail

usage() { echo "usage: pingpong.sh IN_VIDEO OUT_DIR [MAX_WIDTH=1920] | --self-test" >&2; exit 2; }
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo "ffmpeg/ffprobe not found" >&2; exit 1; }

encode() {
  local in=$1 out=$2 w=${3:-1920} name
  [ -f "$in" ] || { echo "no such file: $in" >&2; exit 1; }
  mkdir -p "$out"
  name=$(basename "${in%.*}")
  ffmpeg -loglevel error -y -i "$in" \
    -filter_complex "[0:v]scale='min($w,iw)':-2,setsar=1,split[f][b];[b]reverse[r];[f][r]concat=n=2:v=1:a=0,format=yuv420p" \
    -an -c:v libx264 -crf 23 -preset slow -movflags +faststart "$out/$name.mp4"
  ffmpeg -loglevel error -y -i "$out/$name.mp4" -an -c:v libvpx-vp9 -crf 34 -b:v 0 "$out/$name.webm"
  ffmpeg -loglevel error -y -i "$in" -frames:v 1 -vf "scale='min($w,iw)':-2" -q:v 3 "$out/$name.jpg"
  echo "$out/$name.mp4 $out/$name.webm $out/$name.jpg"
}

duration() { ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

self_test() {
  local dir
  dir=$(mktemp -d)
  trap "rm -rf '$dir'" EXIT
  ffmpeg -loglevel error -y -f lavfi -i testsrc=duration=2:size=320x180:rate=30 -c:v libx264 -pix_fmt yuv420p "$dir/clip.mp4"
  encode "$dir/clip.mp4" "$dir/out" >/dev/null
  for f in clip.mp4 clip.webm clip.jpg; do [ -s "$dir/out/$f" ] || { echo "missing $f" >&2; exit 1; }; done
  # Expected from the input, not from the code under test: 2 s forward + 2 s reversed.
  awk -v d="$(duration "$dir/out/clip.mp4")" 'BEGIN { exit !(d > 3.8 && d < 4.2) }' || { echo "mp4 is not ~4 s" >&2; exit 1; }
  awk -v d="$(duration "$dir/out/clip.webm")" 'BEGIN { exit !(d > 3.8 && d < 4.2) }' || { echo "webm is not ~4 s" >&2; exit 1; }
  echo "self-test ok"
}

case "${1:-}" in
  --self-test) self_test ;;
  ""|-h|--help) usage ;;
  *) [ $# -ge 2 ] || usage; encode "$@" ;;
esac
