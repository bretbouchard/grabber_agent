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
from ai.langfuse_integration import trace_llm_call, span


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Grabber Agent - YouTube Music Integration"
    )
    parser.add_argument("--api-port", type=int, default=8001,
                       help="Port for the API server")
    parser.add_argument("--config", type=str, default="config.yml",
                       help="Path to config file")
    parser.add_argument("--interval", type=int, default=1800,
                       help="Polling interval in seconds (default: 30 minutes)")
    parser.add_argument("--no-daemon", action="store_true",
                       help="Don't run as a daemon (run once and exit)")
    parser.add_argument("--force", action="store_true",
                       help="Force checking even if cache is still valid")
    
    return parser.parse_args()


async def main():
    """Main entry point with Langfuse tracing."""
    args = parse_args()
    # Initialize components
    youtube_client = YouTubeClient(config_path=args.config)
    downloader = AudioDownloader(output_dir="downloads")
    analyzer = AnalyzerIntegration()
    if args.no_daemon:
        # Run once
        with span("grabber_agent_run_once", metadata={"agent": "grabber_agent"}):
            await run_once(youtube_client, downloader, analyzer)
            trace_llm_call(
                name="grabber_agent_run_once",
                input={"args": vars(args)},
                output="run_once completed",
                metadata={"agent": "grabber_agent"}
            )
    else:
        # Run in a loop
        while True:
            try:
                with span("grabber_agent_loop", metadata={"agent": "grabber_agent"}):
                    await run_once(youtube_client, downloader, analyzer)
                    trace_llm_call(
                        name="grabber_agent_loop",
                        input={"args": vars(args)},
                        output="run_once completed",
                        metadata={"agent": "grabber_agent"}
                    )
                logger.info("Process completed successfully")
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            interval = args.interval if args.interval else 1800
            logger.info(f"Sleeping for {interval} seconds")
            await asyncio.sleep(interval)


async def run_once(youtube_client, downloader, analyzer):
    """Run the grabber agent workflow once, with tracing for each video."""
    liked_videos = await youtube_client.get_youtube_music_likes()
    new_videos = youtube_client.filter_new_videos(liked_videos)
    if not new_videos:
        logger.info("No new liked videos found")
        return
    logger.info(f"Found {len(new_videos)} new liked songs from YouTube Music")
    for video in new_videos:
        try:
            with span("grabber_agent_process_video", metadata={"agent": "grabber_agent", "video_id": video['id']}):
                audio_path = await downloader.download_audio(video['id'])
                os.environ["ANALYZER_INTEGRATION_METHOD"] = "file"
                os.environ["ANALYZER_WATCH_DIR"] = "/tmp/analyzer_watch"
                await analyzer.send_audio(audio_path, video)
                youtube_client.mark_as_processed(video['id'])
                trace_llm_call(
                    name="grabber_agent_process_video",
                    input={"video": video},
                    output="processed",
                    metadata={"agent": "grabber_agent", "video_id": video['id']}
                )
        except Exception as e:
            logger.error(f"Error processing video {video['id']}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
