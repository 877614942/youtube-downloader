from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import logging
from datetime import datetime
from flask import Response
import json
import cloudscraper
from fake_useragent import UserAgent
import random

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

def get_random_user_agent():
    try:
        ua = UserAgent()
        return ua.random
    except:
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'

def get_cookies():
    try:
        scraper = cloudscraper.create_scraper()
        response = scraper.get('https://www.youtube.com')
        return '; '.join([f'{k}={v}' for k, v in response.cookies.items()])
    except:
        return ''

# 免费代理列表
PROXY_LIST = [
    'socks5://192.252.208.67:14287',
    'socks5://192.252.211.197:14287',
    'socks5://192.252.214.20:15864',
    'socks5://192.252.209.155:14287',
    'socks5://192.252.208.70:14287'
]

def get_random_proxy():
    return random.choice(PROXY_LIST)

def get_video_info(url):
    try:
        proxy = get_random_proxy()
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'proxy': proxy,
            'http_headers': {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cookie': get_cookies(),
                'Referer': 'https://www.youtube.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        # 如果第一个代理失败，尝试其他代理
        for proxy in PROXY_LIST:
            try:
                ydl_opts['proxy'] = proxy
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)
            except:
                continue
        raise e

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-video-info', methods=['POST'])
def get_video_formats():
    try:
        url = request.json.get('url', '')
        if not url:
            return jsonify({'error': '请提供视频URL'}), 400

        info = get_video_info(url)
        if not info:
            return jsonify({'error': '无法获取视频信息'}), 400

        formats = []
        for f in info.get('formats', []):
            if f.get('format_id') and f.get('ext'):
                format_info = {
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'format': f.get('format'),
                    'filesize': f.get('filesize', 0),
                    'resolution': f.get('resolution', 'N/A')
                }
                formats.append(format_info)

        return jsonify({
            'title': info.get('title', '未知标题'),
            'thumbnail': info.get('thumbnail', ''),
            'formats': formats
        })
    except Exception as e:
        return jsonify({'error': f'错误：{str(e)}'}), 400

# 全局变量存储下载进度
download_progress = {'status': '', 'percent': 0, 'speed': '', 'eta': ''}

@app.route('/get-progress')
def get_progress():
    return jsonify(download_progress)

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.json.get('url', '')
        video_format = request.json.get('format', 'best')
        if not url:
            return jsonify({'error': '请提供视频URL'}), 400

        proxy = get_random_proxy()
        ydl_opts = {
            'format': video_format,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'proxy': proxy,
            'progress_hooks': [my_hook],
            'http_headers': {
                'User-Agent': get_random_user_agent(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Cookie': get_cookies(),
                'Referer': 'https://www.youtube.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            }
        }
        
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
            
            if os.path.exists(os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')):
                file_size = os.path.getsize(os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'))
                logger.info(f"File successfully created. Size: {file_size} bytes")
                return jsonify({
                    'success': True,
                    'filename': '%(title)s.%(ext)s',
                    'download_path': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                    'file_size': file_size
                })
            else:
                logger.error(f"File not found after download: {os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s')}")
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
