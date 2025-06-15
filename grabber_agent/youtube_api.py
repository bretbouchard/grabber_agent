"""
YouTube API integration module for Grabber Agent.
Handles authentication and API requests to the YouTube Data API.
Implements quota optimization strategies.
"""

import os
import json
import yaml
import time
import asyncio
import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class YouTubeClient:
    """YouTube API client for accessing liked videos with quota optimization."""
    
    def __init__(self, config_path: str = "config.yml"):
        """Initialize the YouTube client."""
        self.config_path = config_path
        self.config = self._load_config()
        self.credentials = None
        self.api_key = self.config.get("youtube", {}).get("api_key")
        self.token_file = Path("youtube_token.json")
        self.processed_file = Path("processed_videos.json")
        self.cache_file = Path("youtube_cache.json")
        self.processed_videos = self._load_processed_videos()
        self._service = None
        
        # Cache settings
        self.cache_data = self._load_cache()
        self.cache_ttl = self.config.get("youtube", {}).get("cache_ttl", 86400)  # 24 hours default
        self.last_request_time = 0
        self.min_request_interval = 1.0  # seconds between requests to avoid rate limits
        self.max_results_per_request = 10  # Reduced from 50 to save quota
    
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def _load_processed_videos(self) -> List[str]:
        """Load the list of already processed videos."""
        if self.processed_file.exists():
            with open(self.processed_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_processed_videos(self):
        """Save the list of processed videos."""
        with open(self.processed_file, 'w') as f:
            json.dump(self.processed_videos, f)
    
    def _load_cache(self) -> Dict:
        """Load cached API responses."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                    # Check if cache is stale (older than cache_ttl)
                    if cache.get("timestamp", 0) > (time.time() - self.cache_ttl):
                        return cache
            except Exception as e:
                print(f"Error loading cache: {e}")
        return {"timestamp": 0, "liked_videos": []}
    
    def _save_cache(self, liked_videos: List[Dict[str, Any]]):
        """Save API responses to cache."""
        cache = {
            "timestamp": time.time(),
            "liked_videos": liked_videos
        }
        with open(self.cache_file, 'w') as f:
            json.dump(cache, f)
    
    def authenticate(self):
        """Authenticate with the YouTube API."""
        # Try to load saved credentials
        if self.token_file.exists():
            with open(self.token_file, 'r') as token:
                creds_data = json.load(token)
                self.credentials = Credentials.from_authorized_user_info(creds_data)
        
        # If credentials are missing or invalid, run the OAuth flow
        if not self.credentials or not self.credentials.valid:
            if (self.credentials and self.credentials.expired and 
                    self.credentials.refresh_token):
                self.credentials.refresh(Request())
            else:
                # Use client secrets from config
                client_secrets = self.config.get("youtube", {}).get(
                    "client_secrets", {})
                if not client_secrets:
                    raise ValueError("No client secrets found in config")
                
                # Create a temporary client_secrets.json file
                with open("client_secrets.json", 'w') as f:
                    json.dump({
                        "installed": {
                            "client_id": client_secrets.get("client_id"),
                            "project_id": client_secrets.get("project_id"),
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": 
                                "https://www.googleapis.com/oauth2/v1/certs",
                            "client_secret": client_secrets.get("client_secret"),
                            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", 
                                             "http://localhost"]
                        }
                    }, f)
                
                # Run the OAuth flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    "client_secrets.json",
                    scopes=["https://www.googleapis.com/auth/youtube.readonly"]
                )
                self.credentials = flow.run_local_server(port=0)
                
                # Delete the temporary file
                os.remove("client_secrets.json")
            
            # Save credentials
            with open(self.token_file, 'w') as token:
                token.write(self.credentials.to_json())
    
    def _rate_limit(self):
        """Implement rate limiting to avoid quota exhaustion."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    @property
    def service(self):
        """Get the YouTube API service."""
        if self._service is None:
            # If we have an API key, use that
            if self.api_key:
                self._service = build('youtube', 'v3', developerKey=self.api_key,
                                      cache_discovery=False)
            # Otherwise use OAuth
            else:
                self.authenticate()
                self._service = build('youtube', 'v3', credentials=self.credentials,
                                      cache_discovery=False)
        
        return self._service
    
    async def get_liked_videos(self) -> List[Dict[str, Any]]:
        """Get liked videos for the authenticated user with caching."""
        # Check if we have a valid cache
        if self.cache_data.get("timestamp", 0) > (time.time() - self.cache_ttl):
            print("Using cached liked videos data")
            return self.cache_data.get("liked_videos", [])
        
        # No valid cache, fetch from API
        loop = asyncio.get_event_loop()
        
        # Function to run in executor
        def _get_likes() -> List[Dict[str, Any]]:
            result = []
            next_page_token = None
            page_count = 0
            max_pages = 3  # Limit number of pages to avoid quota depletion
            
            try:
                while page_count < max_pages:
                    # Apply rate limiting
                    self._rate_limit()
                    
                    # Use either OAuth or API key depending on what's available
                    if self.api_key:
                        # With API key we can only get public likes
                        request = self.service.videos().list(
                            part="snippet,contentDetails",
                            myRating="like",
                            maxResults=self.max_results_per_request,
                            pageToken=next_page_token
                        )
                    else:
                        # With OAuth we can get all likes
                        request = self.service.videos().list(
                            part="snippet,contentDetails",
                            myRating="like",
                            maxResults=self.max_results_per_request,
                            pageToken=next_page_token
                        )
                    
                    response = request.execute()
                    result.extend(response['items'])
                    
                    next_page_token = response.get('nextPageToken')
                    page_count += 1
                    
                    if not next_page_token:
                        break
                    
                    # Add extra delay between page requests
                    time.sleep(2)
                
            except HttpError as e:
                print(f"YouTube API error: {e}")
                # If we hit a quota error, try to use cache even if expired
                if "quotaExceeded" in str(e) and self.cache_data.get("liked_videos"):
                    print("Quota exceeded - using expired cache data")
                    return self.cache_data.get("liked_videos", [])
                raise
                
            # Save to cache
            self._save_cache(result)
            return result
        
        # Run API call in executor to avoid blocking
        return await loop.run_in_executor(None, _get_likes)
    
    def filter_new_videos(self, videos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out already processed videos and non-music videos if configured."""
        # First, filter out already processed videos
        new_videos = [video for video in videos 
                     if video['id'] not in self.processed_videos]
        
        # Check if we want to filter for music only
        filter_music_only = self.config.get("youtube", {}).get("filter_music_only", False)
        if filter_music_only:
            # Look for music-related categories or keywords in title/channel
            music_videos = []
            for video in new_videos:
                snippet = video.get("snippet", {})
                title = snippet.get("title", "").lower()
                channel = snippet.get("channelTitle", "").lower()
                category_id = snippet.get("categoryId", "")
                
                # Category ID 10 is Music on YouTube
                is_music = (category_id == "10" or
                           "music" in channel or
                           "song" in title or
                           "audio" in title or
                           "remix" in title or
                           "track" in title)
                
                if is_music:
                    music_videos.append(video)
            
            return music_videos
        else:
            return new_videos
    
    def mark_as_processed(self, video_id: str):
        """Mark a video as processed."""
        if video_id not in self.processed_videos:
            self.processed_videos.append(video_id)
            self._save_processed_videos()
