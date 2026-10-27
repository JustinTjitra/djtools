# dj-tools

Automations and small tools for my DJ workflow: sourcing, organizing, and prepping tracks.

## Tools

| Tool | What it does |
|------|--------------|
| [`soundcloud/sc-playlist.sh`](soundcloud/sc-playlist.sh) | Downloads every track on a public SoundCloud playlist with yt-dlp. Tags, numbers, and adds cover art. Re-runs only fetch new tracks. |

## Requirements

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [ffmpeg](https://ffmpeg.org/) (`brew install yt-dlp ffmpeg`)

## soundcloud/sc-playlist.sh

```bash
./soundcloud/sc-playlist.sh "https://soundcloud.com/artist/sets/playlist" ~/Music/sc
FORMAT=best ./soundcloud/sc-playlist.sh <url>   # keep original stream, no transcode
```

Notes:
- SoundCloud streams are lossy (~128kbps MP3 or ~160kbps Opus/AAC). `FORMAT=best` avoids a lossy-to-lossy transcode; MP3 is the default only for CDJ/DJ-software compatibility.
- Go+ exclusives download as 30s previews; geo-blocked and private tracks are skipped.
- Downloaded track IDs are logged in `<output-dir>/.archive.txt`.

Only download content you have the rights to use.
