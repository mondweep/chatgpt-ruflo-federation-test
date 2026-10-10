#!/usr/bin/env bash
# Reproducible build for mondweep-ruflo-journey.mp4 (1080x1920, 30 fps, ~24 s).
# Requirements: ffmpeg/ffprobe (libx264 + aac), python3 with numpy + Pillow,
# DejaVu fonts. No network access; all visuals and audio are synthesized.
set -euo pipefail
cd "$(dirname "$0")"

OUT=mondweep-ruflo-journey.mp4
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "[1/3] Synthesizing audio"
python3 render.py audio "$TMP/audio.wav"

echo "[2/3] Rendering frames + encoding"
python3 render.py frames | ffmpeg -hide_banner -loglevel error -y \
  -f rawvideo -pix_fmt rgb24 -s 1080x1920 -r 30 -i - \
  -i "$TMP/audio.wav" \
  -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 18 -profile:v high -pix_fmt yuv420p \
  -af "loudnorm=I=-20:TP=-3:LRA=11,aresample=48000" \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart -shortest "$OUT"

echo "[3/3] Verifying"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate \
  -show_entries format=duration,size -of compact "$OUT"
