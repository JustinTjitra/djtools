#!/usr/bin/env bash
# Download every track on a public SoundCloud playlist with yt-dlp.
#
# Usage:
#   ./sc-playlist.sh <playlist-url> [output-dir]
#
# Env overrides:
#   FORMAT=mp3     audio format: mp3 | m4a | opus | flac | best (best = keep original, no re-encode)
#   SLEEP_MIN=1    min seconds between tracks (be polite, avoid rate limits)
#   SLEEP_MAX=3    max seconds between tracks
#
# Re-running on the same playlist only grabs new tracks (tracked in .archive.txt).

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <soundcloud-playlist-url> [output-dir]" >&2
  exit 1
fi

URL="$1"
OUT="${2:-./soundcloud}"
FORMAT="${FORMAT:-mp3}"
SLEEP_MIN="${SLEEP_MIN:-1}"
SLEEP_MAX="${SLEEP_MAX:-3}"

for bin in yt-dlp ffmpeg; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "Missing dependency: $bin" >&2
    echo "  macOS:  brew install yt-dlp ffmpeg" >&2
    echo "  pip:    pip install -U yt-dlp   (ffmpeg via your package manager)" >&2
    exit 1
  fi
done

if [[ "$URL" != *soundcloud.com/*/sets/* ]]; then
  echo "Warning: URL doesn't look like a SoundCloud playlist (/sets/). Continuing anyway." >&2
fi

mkdir -p "$OUT"

yt-dlp \
  --yes-playlist \
  --ignore-errors \
  --no-overwrites \
  --download-archive "$OUT/.archive.txt" \
  -f "bestaudio/best" \
  -x --audio-format "$FORMAT" --audio-quality 0 \
  --embed-metadata \
  --parse-metadata "playlist_title:%(album)s" \
  --parse-metadata "playlist_index:%(track_number)s" \
  --embed-thumbnail --convert-thumbnails jpg \
  --sleep-interval "$SLEEP_MIN" --max-sleep-interval "$SLEEP_MAX" \
  -o "$OUT/%(playlist_title)s/%(playlist_index)03d - %(uploader)s - %(title)s.%(ext)s" \
  "$URL"

echo "Done. Files are in: $OUT"
