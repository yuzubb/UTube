import json
import requests
from flask import Flask, render_template, abort, request

try:
    with open('invidious.txt', 'r') as f:
        INVIDIOUS_INSTANCES = json.load(f)
except FileNotFoundError:
    INVIDIOUS_INSTANCES = []

AVAILABLE_INSTANCES = list(INVIDIOUS_INSTANCES)

app = Flask(__name__)

def get_successful_response(api_path):
    global AVAILABLE_INSTANCES
    
    if not AVAILABLE_INSTANCES:
        AVAILABLE_INSTANCES = list(INVIDIOUS_INSTANCES)
        if not AVAILABLE_INSTANCES:
            return None 

    for base_url in list(AVAILABLE_INSTANCES):
        url = f"{base_url.rstrip('/')}/api/v1/{api_path.lstrip('/')}"
        print(f"Attempting API call: {url}")

        try:
            response = requests.get(url, timeout=5) 
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"Error accessing {base_url}: {e}")
            if base_url in AVAILABLE_INSTANCES:
                AVAILABLE_INSTANCES.remove(base_url)
    
    return None

def format_duration(seconds):
    if seconds is None:
        return ""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    else:
        return f"{m:d}:{s:02d}"

def format_views(count):
    if count is None or not isinstance(count, (int, float)):
        return ""
    count = int(count)
    if count >= 1_000_000:
        return f"{round(count / 1_0000, 1):g}万回"
    elif count >= 1_0000:
        return f"{round(count / 1_0000, 1):g}万回"
    elif count >= 1_000:
        return f"{round(count / 1000, 1):g}千回"
    else:
        return f"{count}回"

app.jinja_env.filters['format_duration'] = format_duration
app.jinja_env.filters['format_views'] = format_views

@app.route('/')
def home():
    data = get_successful_response('trending')
    if data is None:
        abort(503) 
    return render_template('index.html', videos=data)

@app.route('/watch/<video_id>')
def watch(video_id):
    api_path = f'videos/{video_id}'
    video_data = get_successful_response(api_path)

    if video_data is None:
        abort(503)
    if 'error' in video_data:
        abort(404) 

    best_stream_url = None
    TARGET_QUALITY = "360p" 

    if 'formatStreams' in video_data:
        for stream in video_data['formatStreams']:
            if stream.get('container') == 'mp4' and stream.get('qualityLabel') == TARGET_QUALITY:
                best_stream_url = stream.get('url')
                break 
        
        if not best_stream_url:
            for stream in video_data['formatStreams']:
                if stream.get('container') == 'mp4':
                    best_stream_url = stream.get('url')
                    break

    related_videos = video_data.get('relatedVideos', [])

    return render_template(
        'watch.html', 
        video=video_data,
        related_videos=related_videos,
        video_stream_url=best_stream_url 
    )

@app.route('/search')
def search():
    query = request.args.get('q') 
    
    if not query:
        return render_template('results.html', query="", videos=[])

    api_path = f'search?q={query}&type=video'
    search_results = get_successful_response(api_path)

    if search_results is None:
        abort(503) 
        
    return render_template('results.html', query=query, videos=search_results)

@app.route('/channel/<channel_id>')
def channel(channel_id):
    api_path_info = f'channels/{channel_id}'
    channel_data = get_successful_response(api_path_info)

    if channel_data is None:
        abort(503)
    if 'error' in channel_data:
        abort(404) 

    channel_videos = channel_data.get('latestVideos', []) 

    return render_template(
        'channel.html', 
        channel=channel_data,
        videos=channel_videos
    )

@app.errorhandler(503)
def service_unavailable(error):
    return render_template('error.html', code=503, message="現在、Invidiousのエンドポイントに接続できません。しばらくしてから再度お試しください。"), 503

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', code=404, message="お探しのコンテンツは見つかりませんでした。"), 404

if __name__ == '__main__':
    app.run(debug=True)
