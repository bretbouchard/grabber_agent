# Grabber Agent

A YouTube Music integration agent for the Agent Shell system. This agent monitors your YouTube Music account for new liked videos, downloads the audio using `yt-dlp`, and sends it to an Analyzer Agent for further processing.

## Features

- Monitor YouTube Music liked videos via YouTube Data API
- Download audio content using `yt-dlp`
- Convert to MP3 format for processing
- Integration with Analyzer Agent for further processing
- Secure token management for YouTube API access

## Setup

1. Create YouTube Data API credentials
2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your API keys in config.yml
4. Run the agent:
   ```bash
   python main.py
   ```

## Configuration

Create a `config.yml` file with the following structure:

```yaml
youtube:
  # Option 1: Use API key (only access to public videos)
  api_key: "YOUR_API_KEY"
  
  # Option 2: Use OAuth (access to all videos)
  client_secrets:
    client_id: "YOUR_CLIENT_ID"
    client_secret: "YOUR_CLIENT_SECRET"
    project_id: "YOUR_PROJECT_ID"
```

## Integration Methods

The Grabber Agent can send audio to the Analyzer Agent using different methods:

1. **Direct POST** - Default method, sends audio via HTTP POST
2. **File Watcher** - Places files in a watched directory
3. **Message Queue** - Sends notifications via Redis or RabbitMQ

Set the desired method with the `ANALYZER_INTEGRATION_METHOD` environment variable:

```bash
export ANALYZER_INTEGRATION_METHOD=post  # Options: post, file, queue
```

## Documentation

For detailed implementation guide, see [Grabber Agent Guide](docs/grabber_agent_guide.md).
