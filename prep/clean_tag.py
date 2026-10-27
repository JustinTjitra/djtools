#!/usr/bin/env python3
"""Clean SoundCloud-style junk out of track tags and add BPM + key.

Usage:
    python3 prep/clean_tag.py <folder> [--dry-run] [--no-analyze] [--rename]
                                       [--key-format camelot|musical] [--force]

What it does, per audio file (mp3, m4a, flac, opus, ogg):
  1. Title cleanup: strips "FREE DL", "[Free Download]", "Premiere:", "OUT NOW",
     "Buy = Free DL" and similar promo noise.
  2. Artist fix: SoundCloud tags the uploader as artist. When the title looks like
     "Artist - Track" (typical of label/repost channels), the artist is pulled from
     the title and the title shortened to "Track".
  3. Analysis (essentia): writes BPM and key tags. Key uses the EDM-tuned profile.
     Skips files that already have both unless --force.
  4. --rename: renames files to "Artist - Title.ext".

Requires: pip install mutagen essentia numpy, plus ffmpeg on PATH
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.easymp4 import EasyMP4Tags
except ImportError:
    sys.exit("Missing dependency: pip install mutagen")

EasyID3.RegisterTextKey("initialkey", "TKEY")
EasyMP4Tags.RegisterFreeformKey("initialkey", "initialkey")

AUDIO_EXTS = {".mp3", ".m4a", ".flac", ".opus", ".ogg"}

# Promo noise SoundCloud uploaders put in titles. Order matters: bracketed first.
JUNK_PATTERNS = [
    r"[\[\(\{][^\]\)\}]*\b(free\s*(dl|download)|premiere|out\s*now|buy\s*=|"
    r"click\s*buy|supported\s*by|support(ed)?\s*by)\b[^\]\)\}]*[\]\)\}]",
    r"^\s*(premiere|exclusive|free\s*(dl|download))\s*[:|\-]\s*",
    r"\s*[|\-/]\s*(free\s*(dl|download)|out\s*now)\s*$",
    r"\b(free\s*(dl|download))\b\s*$",
    r"\s*\*+\s*free\s*(dl|download)\s*\*+",
]
JUNK_RE = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]
MIX_SUFFIX_RE = re.compile(
    r"^[\w\s'&.]*\b(original|extended|radio|club|dub|vip|edit|remix|mix|bootleg|flip|rework)\b[\w\s'&.]*$",
    re.IGNORECASE,
)

# Essentia key -> Camelot
CAMELOT = {
    ("C", "major"): "8B", ("G", "major"): "9B", ("D", "major"): "10B",
    ("A", "major"): "11B", ("E", "major"): "12B", ("B", "major"): "1B",
    ("F#", "major"): "2B", ("Gb", "major"): "2B", ("C#", "major"): "3B",
    ("Db", "major"): "3B", ("G#", "major"): "4B", ("Ab", "major"): "4B",
    ("D#", "major"): "5B", ("Eb", "major"): "5B", ("A#", "major"): "6B",
    ("Bb", "major"): "6B", ("F", "major"): "7B",
    ("A", "minor"): "8A", ("E", "minor"): "9A", ("B", "minor"): "10A",
    ("F#", "minor"): "11A", ("Gb", "minor"): "11A", ("C#", "minor"): "12A",
    ("Db", "minor"): "12A", ("G#", "minor"): "1A", ("Ab", "minor"): "1A",
    ("D#", "minor"): "2A", ("Eb", "minor"): "2A", ("A#", "minor"): "3A",
    ("Bb", "minor"): "3A", ("F", "minor"): "4A", ("C", "minor"): "5A",
    ("G", "minor"): "6A", ("D", "minor"): "7A",
}


def clean_title(title: str) -> str:
    t = title
    for rx in JUNK_RE:
        t = rx.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"\(\s*\)|\[\s*\]", "", t)
    return t.strip(" -|/\t")


def split_artist(artist: str, title: str):
    """If the title embeds 'Artist - Track', return (artist, track). Else None."""
    m = re.match(r"^(?P<a>[^\-–—]+?)\s+[\-–—]\s+(?P<t>.+)$", title)
    if not m:
        return None
    left, right = m.group("a").strip(), m.group("t").strip()
    # "Track - Extended Mix" is a version suffix, not "Artist - Track".
    if MIX_SUFFIX_RE.match(right):
        return None
    return left, right


def decode(path: Path, sr: int = 44100):
    """Decode to mono float32 via ffmpeg. Essentia's own loader segfaults on some
    formats (Opus), which would kill the whole batch, so we never use it."""
    import subprocess
    import numpy as np
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1",
         "-ar", str(sr), "-"],
        capture_output=True, check=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def analyze(path: Path):
    import essentia
    essentia.log.infoActive = False
    essentia.log.warningActive = False
    import essentia.standard as es
    audio = decode(path)
    rough_bpm, ticks, *_ = es.RhythmExtractor2013(method="multifeature")(audio)
    bpm = refine_bpm(float(rough_bpm), ticks)
    key, scale, strength = es.KeyExtractor(profileType="edma")(audio)
    return round(bpm), key, scale, float(strength)


def refine_bpm(rough_bpm: float, ticks) -> float:
    """Essentia's global BPM is often off by ~0.5-1 because beat times are quantized
    to ~11.6 ms frames. Fitting a line through all beat times averages that out.
    Beats are numbered by their slot on the rough grid, so beats the tracker missed
    (breakdowns) leave gaps instead of shifting every later index."""
    import numpy as np
    ticks = np.asarray(ticks, dtype=float)
    if len(ticks) < 8 or rough_bpm <= 0:
        return rough_bpm
    period = 60.0 / rough_bpm
    # Count beats per gap locally (a gap is short, so the rough period is accurate
    # enough), then accumulate. Numbering against one global grid drifts instead.
    gaps = np.maximum(np.round(np.diff(ticks) / period), 1)
    slots = np.concatenate([[0], np.cumsum(gaps)])
    for _ in range(2):  # re-count with the improved period
        slope = np.polyfit(slots, ticks, 1)[0]
        gaps = np.maximum(np.round(np.diff(ticks) / slope), 1)
        slots = np.concatenate([[0], np.cumsum(gaps)])
    slope = np.polyfit(slots, ticks, 1)[0]
    refined = 60.0 / slope
    # Sanity: refinement should nudge, not jump. Otherwise trust the rough value.
    return refined if abs(refined - rough_bpm) < 2 else rough_bpm


def first(tags, field):
    v = tags.get(field)
    return v[0] if v else ""


def safe_filename(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip()


def process(path: Path, args) -> list[str]:
    f = mutagen.File(path, easy=True)
    if f is None:
        return [f"  skipped: unsupported file"]
    if f.tags is None:
        f.add_tags()
    tags = f.tags
    changes = []

    title = first(tags, "title") or path.stem
    artist = first(tags, "artist")

    new_title = clean_title(title)
    new_artist = artist
    split = split_artist(artist, new_title)
    if split:
        new_artist, new_title = split[0], clean_title(split[1])

    if new_title != title:
        changes.append(f"  title:  {title!r} -> {new_title!r}")
        tags["title"] = new_title
    if new_artist and new_artist != artist:
        changes.append(f"  artist: {artist!r} -> {new_artist!r}")
        tags["artist"] = new_artist

    have_bpm = bool(first(tags, "bpm"))
    have_key = bool(first(tags, "initialkey"))
    if args.analyze and (args.force or not (have_bpm and have_key)):
        try:
            bpm, key, scale, strength = analyze(path)
            if args.key_format == "camelot":
                key_str = CAMELOT.get((key, scale), f"{key}{'m' if scale == 'minor' else ''}")
            else:
                key_str = f"{key}{'m' if scale == 'minor' else ''}"
            tags["bpm"] = str(bpm)
            tags["initialkey"] = key_str
            note = "  (low confidence)" if strength < 0.5 else ""
            changes.append(f"  bpm: {bpm}  key: {key_str}{note}")
        except Exception as e:  # keep going on bad files
            changes.append(f"  analysis failed: {e}")

    if changes and not args.dry_run:
        f.save()

    if args.rename:
        a, t = first(tags, "artist"), first(tags, "title")
        if a and t:
            target = path.with_name(safe_filename(f"{a} - {t}") + path.suffix)
            if target != path:
                if target.exists():
                    changes.append(f"  rename skipped, exists: {target.name}")
                else:
                    changes.append(f"  rename -> {target.name}")
                    if not args.dry_run:
                        path.rename(target)
    return changes


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("folder", type=Path)
    p.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    p.add_argument("--no-analyze", dest="analyze", action="store_false", help="skip BPM/key")
    p.add_argument("--rename", action="store_true", help='rename to "Artist - Title.ext"')
    p.add_argument("--key-format", choices=["camelot", "musical"], default="camelot")
    p.add_argument("--force", action="store_true", help="re-analyze even if tagged")
    args = p.parse_args()

    if args.analyze:
        try:
            import essentia
            essentia.log.infoActive = False
            essentia.log.warningActive = False
        except ImportError:
            sys.exit("Missing dependency for analysis: pip install essentia (or use --no-analyze)")
        import shutil
        if not shutil.which("ffmpeg"):
            sys.exit("Missing dependency for analysis: ffmpeg (brew install ffmpeg)")

    files = sorted(x for x in args.folder.rglob("*") if x.suffix.lower() in AUDIO_EXTS)
    if not files:
        sys.exit(f"No audio files under {args.folder}")

    changed = 0
    for path in files:
        changes = process(path, args)
        if changes:
            changed += 1
            print(path.name)
            print("\n".join(changes))
    verb = "would change" if args.dry_run else "changed"
    print(f"\n{len(files)} files scanned, {changed} {verb}.")


if __name__ == "__main__":
    main()
