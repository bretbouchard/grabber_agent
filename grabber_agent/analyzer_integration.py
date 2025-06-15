"""
Analyzer integration module for Grabber Agent.
Handles sending audio to the Analyzer Agent for processing.
"""

import os
import aiohttp
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class AnalyzerIntegration:
    """Integration with the Analyzer Agent."""
    
    def __init__(self, analyzer_url: str = "http://localhost:8002/analyze"):
        """Initialize the analyzer integration."""
        self.analyzer_url = analyzer_url
    
    async def send_audio(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """Send audio to the analyzer agent."""
        if not audio_path or not audio_path.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return False
        
        logger.info(f"Sending {audio_path} to analyzer")
        
        try:
            # Prepare metadata
            meta = {
                "source": "youtube",
                "video_id": metadata.get("id"),
                "title": metadata.get("snippet", {}).get("title"),
                "channel": metadata.get("snippet", {}).get("channelTitle"),
                "description": metadata.get("snippet", {}).get("description"),
                "published_at": metadata.get("snippet", {}).get("publishedAt"),
            }
            
            # Determine integration method
            integration_method = os.environ.get("ANALYZER_INTEGRATION_METHOD", "post")
            
            if integration_method == "post":
                # Use direct POST with multipart form
                return await self._send_via_post(audio_path, meta)
            elif integration_method == "file":
                # Use file watcher method
                return await self._send_via_file(audio_path, meta)
            elif integration_method == "queue":
                # Use message queue method
                return await self._send_via_queue(audio_path, meta)
            else:
                logger.error(f"Unknown integration method: {integration_method}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending to analyzer: {e}")
            return False
    
    async def _send_via_post(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """Send audio via direct POST."""
        try:
            async with aiohttp.ClientSession() as session:
                # Prepare multipart form data
                data = aiohttp.FormData()
                data.add_field('file',
                               open(audio_path, 'rb'),
                               filename=audio_path.name,
                               content_type='audio/mpeg')
                data.add_field('metadata', json.dumps(metadata))
                
                # Send POST request
                async with session.post(self.analyzer_url, data=data) as response:
                    if response.status == 200:
                        logger.info(f"Successfully sent {audio_path.name} to analyzer")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"Failed to send to analyzer: {response.status}, {text}")
                        return False
        except Exception as e:
            logger.error(f"Error in POST to analyzer: {e}")
            return False
    
    async def _send_via_file(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """Send audio via file watcher method."""
        try:
            # Get watch directory from environment or use default
            watch_dir = os.environ.get("ANALYZER_WATCH_DIR", "/tmp/analyzer_watch")
            
            # Create watch directory if it doesn't exist
            Path(watch_dir).mkdir(parents=True, exist_ok=True)
            
            # Copy audio file to watch directory
            import shutil
            dest_path = Path(watch_dir) / audio_path.name
            shutil.copy(audio_path, dest_path)
            
            # Create metadata file
            meta_path = dest_path.with_suffix('.json')
            with open(meta_path, 'w') as f:
                json.dump(metadata, f)
            
            logger.info(f"Copied {audio_path.name} to analyzer watch directory {watch_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Error in file watcher integration: {e}")
            return False
    
    async def _send_via_queue(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """Send audio via message queue."""
        try:
            # Check for Redis or RabbitMQ environment
            if os.environ.get("USE_REDIS", "false").lower() == "true":
                return await self._send_via_redis(audio_path, metadata)
            else:
                return await self._send_via_rabbitmq(audio_path, metadata)
                
        except Exception as e:
            logger.error(f"Error in queue integration: {e}")
            return False
    
    async def _send_via_redis(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """Send notification via Redis."""
        try:
            import redis
            
            # Get Redis connection details from environment
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            redis_queue = os.environ.get("REDIS_QUEUE", "analyzer_queue")
            
            # Connect to Redis
            r = redis.Redis(host=redis_host, port=redis_port)
            
            # Prepare message
            message = {
                "audio_path": str(audio_path),
                "metadata": metadata
            }
            
            # Publish message
            r.lpush(redis_queue, json.dumps(message))
            logger.info(f"Published {audio_path.name} to Redis queue {redis_queue}")
            return True
            
        except Exception as e:
            logger.error(f"Error in Redis integration: {e}")
            return False
    
    async def _send_via_rabbitmq(self, audio_path: Path, metadata: Dict[str, Any]) -> bool:
        """Send notification via RabbitMQ."""
        try:
            import pika
            
            # Get RabbitMQ connection details from environment
            rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
            rabbitmq_queue = os.environ.get("RABBITMQ_QUEUE", "analyzer_queue")
            
            # Connect to RabbitMQ
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            
            # Declare queue
            channel.queue_declare(queue=rabbitmq_queue, durable=True)
            
            # Prepare message
            message = {
                "audio_path": str(audio_path),
                "metadata": metadata
            }
            
            # Publish message
            channel.basic_publish(
                exchange='',
                routing_key=rabbitmq_queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
            
            connection.close()
            logger.info(f"Published {audio_path.name} to RabbitMQ queue {rabbitmq_queue}")
            return True
            
        except Exception as e:
            logger.error(f"Error in RabbitMQ integration: {e}")
            return False
