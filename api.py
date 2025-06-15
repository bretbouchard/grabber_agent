"""
API module for Grabber Agent.
Provides REST API endpoints for interacting with the Grabber Agent.
"""

import asyncio
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional

from grabber_agent.youtube_api import YouTubeClient
from grabber_agent.downloader import AudioDownloader

# Initialize API
app = FastAPI(title="Grabber Agent API", description="YouTube Music Integration API")

# Initialize components
youtube_client = None
downloader = None


class VideoItem(BaseModel):
    video_id: str
    title: Optional[str] = None
    channel: Optional[str] = None
    url: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global youtube_client, downloader
    youtube_client = YouTubeClient(config_path="config.yml")
    downloader = AudioDownloader(output_dir="downloads")


@app.get("/liked", response_model=List[VideoItem])
async def get_liked_videos():
    """Get all liked videos."""
    try:
        liked_videos = await youtube_client.get_liked_videos()
        return [
            VideoItem(
                video_id=video["id"], 
                title=video["snippet"]["title"],
                channel=video["snippet"]["channelTitle"],
                url=f"https://www.youtube.com/watch?v={video['id']}"
            ) 
            for video in liked_videos
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download/{video_id}")
async def download_video(video_id: str, background_tasks: BackgroundTasks):
    """Download a specific video."""
    try:
        # Queue download in background
        background_tasks.add_task(downloader.download_audio, video_id)
        return {"status": "download queued", "video_id": video_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process")
async def process_new_videos(background_tasks: BackgroundTasks):
    """Process all new liked videos."""
    try:
        # Queue processing in background
        background_tasks.add_task(process_all_new)
        return {"status": "processing queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_all_new():
    """Process all new videos in the background."""
    from grabber_agent.analyzer_integration import AnalyzerIntegration
    analyzer = AnalyzerIntegration()
    
    # Get liked videos
    liked_videos = await youtube_client.get_liked_videos()
    
    # Filter new videos
    new_videos = youtube_client.filter_new_videos(liked_videos)
    
    for video in new_videos:
        try:
            # Download audio
            audio_path = await downloader.download_audio(video['id'])
            
            # Send to analyzer
            await analyzer.send_audio(audio_path, video)
            
            # Mark as processed
            youtube_client.mark_as_processed(video['id'])
        except Exception as e:
            # Log error but continue with next video
            print(f"Error processing video {video['id']}: {e}")
