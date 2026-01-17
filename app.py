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
# Format: {'task_id': {'status': 'processing', 'progress': 0, 'filename': None, 'title': None}}
download_tasks = {}

def progress_hook(d, task_id):
    """
    Callback function that yt-dlp calls while downloading.
    We update the global dictionary with the current percentage.
    """
    if d['status'] == 'downloading':
        # specific string manipulation to extract '15.4%' -> 15.4
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
    """
    Runs in the background. Downloads and converts the file.
    """
    # Use the task_id as the filename on the server (Safe & Simple)
    output_template = f'{DOWNLOAD_FOLDER}/{task_id}.%(ext)s'

    ydl_opts = {
        # FIX: The Format Selector
        # 1. 'bestaudio' = Try to get pure audio first (fastest).
        # 2. 'bestvideo+bestaudio' = If no pure audio, get the best video.
        # 3. 'best' = If all else fails, get whatever is available.
        'format': 'bestaudio/bestvideo+bestaudio/best',
        
        'outtmpl': output_template,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'noplaylist': True,
        
        # 1. AUTHENTICATION: Use the cookies file you uploaded
        'cookiefile': 'cookies.txt',

        # 2. DISGUISE: Tell YouTube we are an Android phone to prevent throttling/empty files
        'extractor_args': {
            'youtube': {
                'player_client': ['android']
            }
        },

        # 3. PROGRESS: Attach the hook to update progress
        'progress_hooks': [lambda d: progress_hook(d, task_id)],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info to get the Real Title
            info = ydl.extract_info(youtube_url, download=True)
            video_title = info.get('title', 'audio_download')

            # The file is guaranteed to be named task_id.mp3
            final_filename = f"{DOWNLOAD_FOLDER}/{task_id}.mp3"
            
            # Update task with the final filename and title so the user can grab it
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
    # 1. Get URL
    data = request.json
    youtube_url = data.get('url')
    if not youtube_url:
        return jsonify({'error': 'No URL provided'}), 400

    # 2. Create a Task ID
    task_id = str(uuid.uuid4())
    download_tasks[task_id] = {'status': 'queued', 'progress': 0}

    # 3. Start Download in Background Thread
    thread = threading.Thread(target=download_thread, args=(youtube_url, task_id))
    thread.start()

    # 4. Return the Task ID to the browser
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    # Browser asks: "How is task X doing?"
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)

@app.route('/get_file/<task_id>', methods=['GET'])
def get_file(task_id):
    # 1. Get task details
    task = download_tasks.get(task_id)
    if not task:
        return "Error: Task not found.", 404
    
    # 2. Check if file exists on server
    file_path = task['filename']
    if not os.path.exists(file_path):
        return "Error: File missing from server.", 404

    # 3. Prepare the user-friendly filename
    # We take the original title, but replace slashes to avoid filesystem errors
    original_title = task.get('title', 'audio_download')
    safe_user_filename = original_title.replace('/', '_').replace('\\', '_') + ".mp3"

    try:
        # 4. Send the file!
        return send_file(
            file_path, 
            as_attachment=True, 
            download_name=safe_user_filename
        )
    except Exception as e:
        return f"Error sending file: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)