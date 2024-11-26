from flask import Flask, render_template, request, jsonify, send_file
import os
from pytube import YouTube
from googleapiclient.discovery import build
import re
import logging
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 在生产环境中使用临时文件夹
DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# YouTube API 密钥
YOUTUBE_API_KEY = 'YOUR_API_KEY_HERE'  # 替换为你的 API 密钥
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

def get_video_id(url):
    """从 URL 中提取视频 ID"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_video_info_from_api(video_id):
    """使用 YouTube API 获取视频信息"""
    try:
        request = youtube.videos().list(
            part="snippet,contentDetails",
            id=video_id
        )
        response = request.execute()
        
        if not response['items']:
            return None
            
        video = response['items'][0]
        return {
            'title': video['snippet']['title'],
            'thumbnail': video['snippet']['thumbnails']['high']['url'],
            'description': video['snippet']['description']
        }
    except Exception as e:
        logger.error(f"Error fetching video info from API: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    try:
        url = request.json.get('url', '')
        if not url:
            return jsonify({'error': '请提供视频URL'}), 400

        video_id = get_video_id(url)
        if not video_id:
            return jsonify({'error': '无效的YouTube URL'}), 400

        # 获取视频信息
        video_info = get_video_info_from_api(video_id)
        if not video_info:
            return jsonify({'error': '无法获取视频信息'}), 400

        # 获取可用的视频流
        yt = YouTube(url)
        streams = []
        
        # 获取视频流信息
        for stream in yt.streams.filter(progressive=True).order_by('resolution').desc():
            streams.append({
                'itag': stream.itag,
                'resolution': stream.resolution,
                'filesize': stream.filesize,
                'mime_type': stream.mime_type
            })

        video_info['formats'] = streams
        return jsonify(video_info)

    except Exception as e:
        logger.error(f"Error in get_video_info: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.json.get('url', '')
        itag = request.json.get('itag')
        
        if not url:
            return jsonify({'error': '请提供视频URL'}), 400

        yt = YouTube(url)
        stream = yt.streams.get_by_itag(itag)
        
        if not stream:
            return jsonify({'error': '无法获取所选格式的视频流'}), 400

        # 下载视频
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{yt.title}.mp4"
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)  # 清理文件名
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        stream.download(output_path=DOWNLOAD_FOLDER, filename=filename)
        
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            return jsonify({
                'success': True,
                'filename': filename,
                'file_size': file_size,
                'download_path': filepath
            })
        else:
            return jsonify({'error': '下载失败'}), 400

    except Exception as e:
        logger.error(f"Error in download_video: {str(e)}")
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)
