"""
Main entry point for Grabber Agent.
YouTube Music integration for agent_shell system.
"""

import sys
import argparse
import asyncio
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from grabber_agent.youtube_api import YouTubeClient
from grabber_agent.downloader import AudioDownloader
from grabber_agent.analyzer_integration import AnalyzerIntegration


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Grabber Agent - YouTube Music Integration"
    )
    parser.add_argument("--api-port", type=int, default=8001,
                       help="Port for the API server")
    parser.add_argument("--config", type=str, default="config.yml",
                       help="Path to config file")
    parser.add_argument("--interval", type=int, default=300,
                       help="Polling interval in seconds")
    parser.add_argument("--no-daemon", action="store_true",
                       help="Don't run as a daemon (run once and exit)")
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Initialize components
    youtube_client = YouTubeClient(config_path=args.config)
    downloader = AudioDownloader(output_dir="downloads")
    analyzer = AnalyzerIntegration()
    
    if args.no_daemon:
        # Run once
        await run_once(youtube_client, downloader, analyzer)
    else:
        # Run in a loop
        while True:
            try:
                await run_once(youtube_client, downloader, analyzer)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            
            logger.info(f"Sleeping for {args.interval} seconds")
            await asyncio.sleep(args.interval)


async def run_once(youtube_client, downloader, analyzer):
    """Run the grabber agent workflow once."""
    # Get liked videos
    liked_videos = await youtube_client.get_liked_videos()
    
    # Filter for new videos
    new_videos = youtube_client.filter_new_videos(liked_videos)
    
    if not new_videos:
        logger.info("No new liked videos found")
        return
    
    logger.info(f"Found {len(new_videos)} new liked videos")
    
    # Process each video
    for video in new_videos:
        try:
            # Download audio
            audio_path = await downloader.download_audio(video['id'])
            
            # Send to analyzer
            await analyzer.send_audio(audio_path, video)
            
            # Mark as processed
            youtube_client.mark_as_processed(video['id'])
            
        except Exception as e:
            logger.error(f"Error processing video {video['id']}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
