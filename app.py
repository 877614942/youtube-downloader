from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import logging
from datetime import datetime
from flask import Response
import json

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# 在生产环境中使用临时文件夹
DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER', 'downloads')

# 设置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 确保下载目录存在
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def clean_filename(filename):
    # 添加时间戳以避免文件名冲突
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
    return f"{timestamp}_{cleaned}"

@app.route('/')
def index():
    return render_template('index.html')

def get_video_formats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'extract_flat': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
        # 优化连接设置
        'socket_timeout': 30,
        'extractor_retries': 5,
        'fragment_retries': 10,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            logger.info(f"Extracting info for URL: {url}")
            info = ydl.extract_info(url, download=False)
            formats = []
            seen_resolutions = set()
            
            # 处理所有可用的格式
            for f in info['formats']:
                # 记录格式信息用于调试
                logger.debug(f"Format found: {f.get('format_id')} - {f.get('ext')} - {f.get('vcodec')} - {f.get('acodec')} - {f.get('height')}p")
                
                # 检查是否为视频格式
                if f.get('vcodec') != 'none':
                    height = f.get('height', 0)
                    
                    # 跳过重复的分辨率
                    if height in seen_resolutions:
                        continue
                    
                    # 查找对应的音频格式
                    audio_format = None
                    for af in info['formats']:
                        if af.get('vcodec') == 'none' and af.get('acodec') != 'none':
                            audio_format = af['format_id']
                            break
                    
                    if height > 0:  # 确保高度值有效
                        seen_resolutions.add(height)
                        format_id = f['format_id']
                        if audio_format:
                            format_id = f"{format_id}+{audio_format}"
                        
                        formats.append({
                            'format_id': format_id,
                            'resolution': f"{height}p",
                            'filesize': f"{int(f.get('filesize', 0) / 1024 / 1024)} MB" if f.get('filesize') else 'unknown'
                        })
            
            # 按分辨率排序（从高到低）
            formats.sort(key=lambda x: int(x['resolution'].replace('p', '')), reverse=True)
            
            logger.info(f"Found {len(formats)} valid formats")
            logger.debug(f"Available formats: {formats}")
            
            return {
                'title': info['title'],
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'author': info.get('uploader', ''),
                'formats': formats
            }
        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            raise

# 全局变量存储下载进度
download_progress = {'status': '', 'percent': 0, 'speed': '', 'eta': ''}

@app.route('/get-progress')
def get_progress():
    return jsonify(download_progress)

@app.route('/get-video-info', methods=['POST'])
def get_video_info():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        # 确保URL是完整的YouTube链接
        if 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]
            url = f'https://www.youtube.com/watch?v={video_id}'

        logger.info(f"Fetching video info for URL: {url}")
        video_info = get_video_formats(url)
        logger.info("Video info prepared successfully")
        return jsonify(video_info)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in get_video_info: {error_msg}", exc_info=True)
        return jsonify({'error': f"Error: {error_msg}"}), 400

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.json.get('url')
        format_id = request.json.get('itag')
        
        if not url or not format_id:
            return jsonify({'error': 'Missing URL or format ID'}), 400

        logger.info(f"Starting download process for URL: {url}")
        logger.info(f"Selected format ID: {format_id}")

        # 确保URL是完整的YouTube链接
        if 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]
            url = f'https://www.youtube.com/watch?v={video_id}'
            logger.info(f"Converted to full URL: {url}")

        # 获取视频信息
        logger.info("Fetching video information...")
        info = get_video_formats(url)
        filename = clean_filename(f"{info['title']}.mp4")
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        logger.info(f"Video will be saved as: {filepath}")
        
        # 确保下载目录存在
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        
        # 获取ffmpeg路径
        ffmpeg_location = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg.exe')
        if not os.path.exists(ffmpeg_location):
            logger.error(f"FFmpeg not found at: {ffmpeg_location}")
            return jsonify({'error': 'FFmpeg not found. Please make sure ffmpeg.exe is in the project directory.'}), 400
        else:
            logger.info(f"Found FFmpeg at: {ffmpeg_location}")
        
        def my_hook(d):
            global download_progress
            if d['status'] == 'downloading':
                download_progress.update({
                    'status': 'downloading',
                    'percent': float(d.get('_percent_str', '0%').replace('%', '')),
                    'speed': d.get('_speed_str', 'unknown speed'),
                    'eta': d.get('_eta_str', 'unknown time')
                })
                logger.info(f"Downloading... {d.get('_percent_str', '0%')} at {d.get('_speed_str', 'unknown speed')}")
            elif d['status'] == 'finished':
                download_progress.update({
                    'status': 'finished',
                    'percent': 100,
                    'speed': '',
                    'eta': ''
                })
                logger.info('Download completed, now converting...')
            elif d['status'] == 'error':
                download_progress.update({
                    'status': 'error',
                    'percent': 0,
                    'speed': '',
                    'eta': ''
                })
                logger.error(f"Error during download: {d.get('error')}")

        ydl_opts = {
            'format': format_id,
            'outtmpl': filepath,
            'quiet': False,
            'no_warnings': False,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'no_color': True,
            'ffmpeg_location': ffmpeg_location,
            'progress_hooks': [my_hook],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
            },
            # 进一步优化下载速度的设置
            'buffersize': 1024 * 1024 * 32,  # 增加到32MB buffer
            'concurrent_fragments': 8,        # 增加到8个并发下载片段
            'file_access_retries': 10,       # 增加文件访问重试次数
            'fragment_retries': 15,          # 增加片段下载重试次数
            'retry_sleep': 2,                # 减少重试间隔
            'socket_timeout': 60,            # 增加Socket超时时间
            'extractor_retries': 10,         # 增加提取器重试次数
            'external_downloader_args': [
                '-c',                        # 支持断点续传
                '--max-connection-per-server', '32',  # 增加到32个连接
                '--min-split-size', '512K',  # 减小分片大小以增加并发
                '--max-concurrent-downloads', '8',  # 最大并发下载数
                '--max-download-limit', '0',  # 不限制下载速度
                '--auto-file-renaming', 'true',  # 自动重命名文件
                '--check-certificate', 'false',  # 禁用证书检查
                '--timeout', '60',  # 连接超时时间
                '--max-tries', '10',  # 最大重试次数
            ],
            'http_chunk_size': 1024 * 1024 * 10,  # 10MB的块大小
            'ratelimit': None,  # 禁用速度限制
            'throttledratelimit': None,  # 禁用节流
        }
        
        try:
            # 重置下载进度
            download_progress.update({
                'status': 'starting',
                'percent': 0,
                'speed': '',
                'eta': ''
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Starting download...")
                ydl.download([url])
                logger.info("Download completed successfully")
            
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                logger.info(f"File successfully created. Size: {file_size} bytes")
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'download_path': filepath,
                    'file_size': file_size
                })
            else:
                logger.error(f"File not found after download: {filepath}")
                return jsonify({'error': 'File not found after download'}), 400
                
        except Exception as e:
            logger.error(f"Error during download/conversion: {str(e)}", exc_info=True)
            return jsonify({'error': f"Download failed: {str(e)}"}), 400
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in download_video: {error_msg}", exc_info=True)
        return jsonify({'error': f"Error: {error_msg}"}), 400

@app.route('/download-file/<path:filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join(DOWNLOAD_FOLDER, filename),
            as_attachment=True
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in download_file: {error_msg}", exc_info=True)
        return jsonify({'error': f"Error: {error_msg}"}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
