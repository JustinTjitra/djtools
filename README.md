# djtools

Automations and small tools for my DJ workflow, organized by stage of the pipeline:

```
ingest/   get tracks in (downloaders)
prep/     clean, tag, analyze before importing into DJ software
```

## Tools

| Stage | Tool | What it does |
|-------|------|--------------|
| ingest | [`sc-playlist.sh`](ingest/sc-playlist.sh) | Downloads every track on a public SoundCloud playlist with yt-dlp. Tags, numbers, adds cover art. Re-runs only fetch new tracks. |
| prep | [`clean_tag.py`](prep/clean_tag.py) | Strips promo junk from titles ("FREE DL", "Premiere:", "OUT NOW"), fixes artist when a label/repost channel uploaded it, writes BPM + key (Camelot) tags, optionally renames to `Artist - Title`. |

## Setup

```bash
brew install yt-dlp ffmpeg
pip install mutagen essentia numpy
```

## Typical run

```bash
./ingest/sc-playlist.sh "https://soundcloud.com/artist/sets/playlist" ~/Music/sc
python3 prep/clean_tag.py ~/Music/sc --dry-run --rename   # preview
python3 prep/clean_tag.py ~/Music/sc --rename             # apply
```

## Notes

### ingest/sc-playlist.sh
- SoundCloud streams are lossy (~128kbps MP3 or ~160kbps Opus/AAC). `FORMAT=best` keeps the original stream and avoids a lossy-to-lossy transcode; MP3 is the default only for CDJ/DJ-software compatibility.
- Go+ exclusives download as 30s previews; geo-blocked and private tracks are skipped.
- Downloaded track IDs are logged in `<output-dir>/.archive.txt`.

### prep/clean_tag.py
- Flags: `--dry-run`, `--rename`, `--no-analyze` (tags only, fast), `--force` (re-analyze already-tagged files), `--key-format musical` (e.g. `Am` instead of `8A`).
- Key detection uses essentia's EDM-tuned profile. Results flagged "low confidence" are worth checking by ear.
- BPM is refined by fitting a line through all detected beats, which removes the ~0.5-1 BPM error essentia's global estimate often has. Rounded to an integer, so tracks at fractional tempos (some older or live-drummed records) will be rounded.
- Artist splitting assumes "Artist - Track" in the title means a repost channel uploaded it. Version suffixes ("Track - Extended Mix", "Track - VIP") are left alone. Check the dry run for edge cases.
- Rekordbox and Serato run their own analysis on import, so the BPM/key tags matter most for browsing files before import, sorting folders, and software that trusts file tags.

Only download content you have the rights to use.
