#!/bin/bash
# Install dependencies
pip install -r requirements.txt

# Create downloads directory
mkdir -p /tmp/downloads

# Download FFmpeg
python download_ffmpeg.py
