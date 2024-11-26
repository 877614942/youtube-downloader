import os
import requests
import zipfile
import shutil
import sys

def download_ffmpeg():
    """Download and setup FFmpeg for the application."""
    print("Downloading FFmpeg...")
    
    # FFmpeg download URL
    ffmpeg_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    # Create temp directory if it doesn't exist
    if not os.path.exists('temp'):
        os.makedirs('temp')
    
    # Download FFmpeg
    response = requests.get(ffmpeg_url, stream=True)
    zip_path = os.path.join('temp', 'ffmpeg.zip')
    
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    print("Extracting FFmpeg...")
    
    # Extract FFmpeg
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall('temp')
    
    # Find the ffmpeg.exe in the extracted files
    ffmpeg_dir = None
    for root, dirs, files in os.walk('temp'):
        if 'ffmpeg.exe' in files:
            ffmpeg_path = os.path.join(root, 'ffmpeg.exe')
            # Copy ffmpeg.exe to the root directory
            shutil.copy2(ffmpeg_path, 'ffmpeg.exe')
            break
    
    # Clean up
    shutil.rmtree('temp')
    print("FFmpeg setup complete!")

if __name__ == "__main__":
    download_ffmpeg()
