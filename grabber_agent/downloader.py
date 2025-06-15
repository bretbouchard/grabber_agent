"""
Audio downloader module for Grabber Agent.
Uses yt-dlp to download audio from YouTube videos.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess

logger = logging.getLogger(__name__)


class AudioDownloader:
    """YouTube audio downloader using yt-dlp."""
    
    def __init__(self, output_dir: str = "downloads", audio_format: str = "mp3"):
        """Initialize the downloader."""
        self.output_dir = Path(output_dir)
        self.audio_format = audio_format
        self.archive_file = self.output_dir / "archive.txt"
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def download_audio(self, video_id: str) -> Optional[Path]:
        """Download audio from a YouTube video."""
        # First check if we already have this file in archive
        if self.archive_file.exists():
            with open(self.archive_file, 'r') as f:
                if f"youtube {video_id}" in f.read():
                    # Find the file that matches this video ID
                    for file in self.output_dir.glob(f"*.{self.audio_format}"):
                        return file

        url = f"https://www.youtube.com/watch?v={video_id}"
        output_template = str(self.output_dir / "%(title)s.%(ext)s")
        
        # Prepare yt-dlp command with optimizations
        cmd = [
            "yt-dlp",
            "-x",  # Extract audio
            "--audio-format", self.audio_format,
            "--audio-quality", "0",  # Best quality
            "--download-archive", str(self.archive_file),
            "--output", output_template,
            "--no-progress",  # No progress bar
            "--force-ipv4",   # More reliable connections
            "--throttled-rate", "100K",  # Be gentle to the server
            "--retries", "3",  # Retry failed downloads
            url
        ]
        
        logger.info(f"Downloading audio from {url}")
        
        # Run yt-dlp in a separate process
        try:
            # Use asyncio subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"yt-dlp error: {stderr.decode()}")
                return None
            
            # Parse output to find the downloaded file path
            output_lines = stdout.decode().splitlines()
            for line in output_lines:
                if self.audio_format in line and "[ExtractAudio]" in line:
                    # Extract the filename
                    parts = line.split("Destination: ")
                    if len(parts) > 1:
                        filename = parts[1].strip()
                        return Path(filename)
            
            # If we couldn't find the exact file, look for any new files with the video ID
            for file in self.output_dir.glob(f"*.{self.audio_format}"):
                # Check if this is a recent file
                if (file.stat().st_mtime > (os.time() - 60)):  # File created in the last minute
                    return file
            
            return None
            
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            return None
