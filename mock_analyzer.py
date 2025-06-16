#!/usr/bin/env python
"""
Mock Analyzer Agent for testing the Grabber Agent.
Runs a simple HTTP server that accepts audio files and metadata.
"""

import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AnalyzerRequestHandler(BaseHTTPRequestHandler):
    """Simple handler to receive file uploads."""
    
    def do_POST(self):
        """Handle POST requests."""
        logger.info("Received POST request")
        
        # Parse form data
        content_type = self.headers.get('Content-Type')
        if not content_type:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Bad Request: No Content-Type')
            return
        
        if 'multipart/form-data' in content_type:
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST',
                        'CONTENT_TYPE': content_type}
            )
            
            # Extract file and metadata
            file_item = form.getvalue('file')
            metadata_json = form.getvalue('metadata')
            
            if not file_item:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Bad Request: No File')
                return
            
            if isinstance(metadata_json, str):
                metadata = json.loads(metadata_json)
            else:
                metadata = {'error': 'No metadata'}
            
            # Process the received file
            logger.info(f"Received file: {metadata.get('title', 'unknown')}")
            logger.info(f"From channel: {metadata.get('channel', 'unknown')}")
            logger.info(f"YouTube ID: {metadata.get('video_id', 'unknown')}")
            
            # Respond with success
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {'status': 'success', 'message': 'File received and processed'}
            self.wfile.write(json.dumps(response).encode('utf-8'))
            return
        
        self.send_response(415)
        self.end_headers()
        self.wfile.write(b'Unsupported Media Type')

def run_server(port=8002):
    """Run the HTTP server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, AnalyzerRequestHandler)
    logger.info(f"Starting mock analyzer server on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
