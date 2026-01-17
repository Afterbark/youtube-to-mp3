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
    # FIX: Use the task_id as the filename on the server (Safe & Simple)
    # This avoids errors with spaces, emojis, or special characters in titles
    output_template = f'{DOWNLOAD_FOLDER}/{task_id}.%(ext)s'

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
        'progress_hooks': [lambda d: progress_hook(d, task_id)],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 1. Extract info to get the Real Title
            info = ydl.extract_info(youtube_url, download=True)
            video_title = info.get('title', 'audio')

            # 2. The file is guaranteed to be named task_id.mp3
            final_filename = f"{DOWNLOAD_FOLDER}/{task_id}.mp3"
            
            # 3. Save info so we can use it later
            download_tasks[task_id]['status'] = 'done'
            download_tasks[task_id]['filename'] = final_filename
            download_tasks[task_id]['title'] = video_title # Save title for the user
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
    if not task or task['status'] != 'done':
        return "File not ready", 400
    
    # FIX: Send the file named "uuid.mp3" but tell the browser to call it "Rick Astley.mp3"
    safe_download_name = f"{task['title']}.mp3"
    
    return send_file(
        task['filename'], 
        as_attachment=True, 
        download_name=safe_download_name
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)