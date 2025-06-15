#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="grabber-agent",
    version="0.1.0",
    description="YouTube Music integration agent for agent_shell",
    author="Bret Bouchard",
    packages=find_packages(),
    install_requires=[
        "google-auth-oauthlib",
        "google-api-python-client",
        "yt-dlp",
        "requests",
        "pydantic",
        "fastapi",
        "python-dotenv",
        "pyyaml",
    ],
    python_requires=">=3.8",
)
