import os
import time
import threading
import uuid
from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp

app = Flask(__name__)

# Ensure a downloads directory exists
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# GLOBAL DICTIONARY TO STORE PROGRESS
download_tasks = {}

def progress_hook(d, task_id):
    if d['status'] == 'downloading':
        p = d.get('_percent_str', '0%').replace('%', '')
        try:
            download_tasks[task_id]['progress'] = float(p)
            download_tasks[task_id]['status'] = 'downloading'
        except ValueError:
            pass
    elif d['status'] == 'finished':
        download_tasks[task_id]['progress'] = 100
        download_tasks[task_id]['status'] = 'converting'

def download_thread(youtube_url, task_id):
    output_template = f'{DOWNLOAD_FOLDER}/{task_id}.%(ext)s'

    ydl_opts = {
        # CRITICAL FIX 1: The "Grab Anything" Selector
        # If 'bestaudio' (pure audio) fails, it will download the VIDEO ('best')
        # and then FFmpeg will strip the audio out. This prevents the "Format not available" error.
        'format': 'bestaudio/bestvideo+bestaudio/best',
        
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
        
        # CRITICAL FIX 2: Android Disguise WITHOUT Cookies
        # We removed 'cookiefile' because it conflicts with the Android client.
        # The Android client usually bypasses the "Sign in" check for music videos.
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },

        'progress_hooks': [lambda d: progress_hook(d, task_id)],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            video_title = info.get('title', 'audio_download')

            final_filename = f"{DOWNLOAD_FOLDER}/{task_id}.mp3"
            
            download_tasks[task_id]['status'] = 'done'
            download_tasks[task_id]['filename'] = final_filename
            download_tasks[task_id]['title'] = video_title
            download_tasks[task_id]['progress'] = 100
            
    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/start_download', methods=['POST'])
def start_download():
    data = request.json
    youtube_url = data.get('url')
    if not youtube_url:
        return jsonify({'error': 'No URL provided'}), 400

    task_id = str(uuid.uuid4())
    download_tasks[task_id] = {'status': 'queued', 'progress': 0}

    thread = threading.Thread(target=download_thread, args=(youtube_url, task_id))
    thread.start()

    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)

@app.route('/get_file/<task_id>', methods=['GET'])
def get_file(task_id):
    task = download_tasks.get(task_id)
    if not task:
        return "Error: Task not found.", 404
    
    file_path = task['filename']
    if not os.path.exists(file_path):
        return "Error: File missing from server.", 404

    original_title = task.get('title', 'audio_download')
    # Remove dangerous characters
    safe_user_filename = original_title.replace('/', '_').replace('\\', '_') + ".mp3"

    try:
        return send_file(
            file_path, 
            as_attachment=True, 
            download_name=safe_user_filename
        )
    except Exception as e:
        return f"Error sending file: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)