# Grabber Agent Implementation Guide

## Overview

The Grabber Agent monitors your YouTube Music account for new liked videos, downloads the audio using `yt-dlp`, and sends it to an Analyzer Agent for further processing in your `agent_shell` system.

## Workflow Summary

1. **Monitor liked videos**
2. **Download new audio via `yt-dlp`**
3. **Send to Analyzer Agent for processing**

---

## 1. YouTube Data API Setup

- Visit the [Google Cloud Console](https://console.cloud.google.com/)
- Create a project and enable **YouTube Data API v3**
- Generate OAuth2 credentials (recommended for user-specific likes)
- Store and refresh the token securely

Use the API to poll:
```
GET https://www.googleapis.com/youtube/v3/videos?myRating=like&part=snippet,contentDetails
```

---

## 2. Download Audio with `yt-dlp`

- Install `yt-dlp`:
  ```bash
  pip install yt-dlp
  ```

- Example usage:
  ```bash
  yt-dlp -x --audio-format mp3 --output "%(title)s.%(ext)s" "https://www.youtube.com/watch?v=VIDEO_ID"
  ```

- Recommended flags:
  - `-x`: extract audio
  - `--audio-format mp3`: convert to MP3
  - `--download-archive archive.txt`: track already downloaded items
  - `--output`: save with clean filenames

---

## 3. Send to Analyzer Agent

Choose from one of the following communication strategies:

### A. File Watcher + HTTP Trigger
- Place the file in a watched directory.
- The Analyzer Agent receives a POST notification with the file path.

### B. Direct POST with Audio
- Use multipart file upload:
  ```python
  requests.post("http://analyzer.local/api/analyze", files={"file": open("song.mp3", "rb")})
  ```

### C. Message Queue
- Use RabbitMQ or Redis to notify Analyzer Agent with the download metadata + filepath.

---

## 4. Automation and Scheduling

- Run the Grabber Agent as a `systemd` service or a Python loop:
  ```python
  while True:
      check_youtube_likes()
      sleep(300)
  ```

- Use `cron` or a job scheduler if needed.

---

## Security Considerations

- Never hardcode secrets.
- Encrypt OAuth tokens and refresh tokens.
- Sanitize filenames before saving.
- Ensure the Analyzer Agent cannot be triggered by arbitrary users.

---

## Optional Features

- Save metadata (title, channel, tags) in JSON alongside audio.
- Auto-tag MP3 files with ID3 metadata.
- Include BPM/key detection pre-pass before forwarding.

---

## Conclusion

The Grabber Agent provides an automated way to sync your YouTube likes with downstream analysis tools. Using `yt-dlp` ensures reliable downloading and audio extraction. The Agent Shell system should cleanly route downloaded content to appropriate analysis agents based on its internal logic.