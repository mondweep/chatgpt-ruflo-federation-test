# Mondweep • Ruflo journey — social video

Vertical motion-graphics clip: `mondweep-ruflo-journey.mp4`
(1080×1920, 30 fps, H.264 High/yuv420p + AAC 48 kHz stereo, 24 s).

## Build

```bash
./social-video/build-video.sh
```

Requires `ffmpeg`/`ffprobe` (libx264, aac), `python3` with `numpy` + `Pillow`,
and DejaVu fonts. Runs offline; renders in roughly 15–30 s on a multi-core machine.

## Files

- `build-video.sh` — synthesizes audio, pipes frames into FFmpeg, verifies with ffprobe.
- `render.py` — deterministic renderer (`frames`, `audio <wav>`, `still <sec> <png>` for previews).

## Content

Eight chapters (opening → closing) with a chapter label and segmented progress line,
moving network nodes, terminal-style cards, and a prompt → route → write →
post-edit → evidence pipeline. All on-screen claims are taken verbatim from the brief.

## Assets and safety

- All visuals are drawn procedurally (no logos, stock media, or downloads).
- Audio is synthesized locally (sine drone, soft 80 bpm pulse, transition bells,
  filtered-noise swells), loudness-normalized to −20 LUFS, true peak −3 dBTP.
- Text is kept inside 100 px side margins and between y = 230–1600 px;
  `render.py` asserts that every wrapped line fits the safe width.
