import json
import os
import re
import urllib.parse
import urllib.request
import ssl
import html
from io import BytesIO
from http.server import BaseHTTPRequestHandler


def send_json(start_response, data, status=200):
    status_text = {
        200: 'OK', 400: 'Bad Request', 405: 'Method Not Allowed',
        500: 'Internal Server Error',
    }
    headers = [
        ('Content-Type', 'application/json'),
        ('Access-Control-Allow-Origin', '*'),
    ]
    start_response(f'{status} {status_text.get(status, "Error")}', headers)
    return [json.dumps(data).encode()]


def extract_video_id(url):
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed.path == '/watch':
            qs = urllib.parse.parse_qs(parsed.query)
            v = qs.get('v', [None])[0]
            if v: return v
        m = re.match(r'^/shorts/([a-zA-Z0-9_-]{11})', parsed.path)
        if m: return m.group(1)
    if parsed.hostname == 'youtu.be':
        path = parsed.path.lstrip('/')
        if path: return path[:11]
    return None


def fetch_youtube_transcript(video_id):
    url = f'https://www.youtube.com/watch?v={video_id}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        page = resp.read().decode('utf-8', errors='replace')
    m = re.search(r'"captionTracks":\s*(\[.*?\])', page)
    if m:
        tracks = json.loads(m.group(1))
        if tracks:
            caption_url = tracks[0].get('baseUrl', '')
            if caption_url:
                req2 = urllib.request.Request(caption_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req2, context=ctx, timeout=15) as resp2:
                    xml_data = resp2.read().decode('utf-8', errors='replace')
                entries = []
                for match in re.finditer(r'<text start="([^"]*)" dur="([^"]*)"[^>]*>(.*?)</text>', xml_data):
                    start = float(match.group(1))
                    text = html.unescape(match.group(3)).replace('\n', ' ').strip()
                    if text: entries.append({'start': start, 'text': text})
                return entries
    raise Exception('No transcript found')


def group_transcript(transcript, group_seconds=45):
    if not transcript: return ''
    paragraphs, current, current_start = [], [], transcript[0].get('start', 0)
    for entry in transcript:
        text = entry.get('text', '').strip()
        if not text: continue
        start = entry.get('start', 0)
        if start - current_start >= group_seconds and current:
            paragraphs.append(' '.join(current))
            current = []
            current_start = start
        current.append(text)
    if current: paragraphs.append(' '.join(current))
    return '\n\n'.join(paragraphs)


def handle_wsgi_request(environ, start_response):
    if environ['REQUEST_METHOD'] != 'POST':
        return send_json(start_response, {'error': 'Method not allowed. Use POST.'}, 405)
    try:
        content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        body = environ['wsgi.input'].read(content_length)
        data = json.loads(body)
        url = (data.get('url') or '').strip()
        video_id = extract_video_id(url)
        if not video_id:
            return send_json(start_response, {'error': 'Invalid URL'})
        try:
            transcript = fetch_youtube_transcript(video_id)
        except Exception as e:
            return send_json(start_response, {'error': f'Transcript error: {e}'})
        raw_text = '\n'.join(e.get('text', '') for e in transcript if e.get('text'))
        formatted = group_transcript(transcript)
        markdown = f'# YouTube Transcript\n\n{formatted}\n\n---\n*Source: {url}*'
        import tiktoken
        enc = tiktoken.get_encoding('cl100k_base')
        original_tokens = len(enc.encode(raw_text))
        markdown_tokens = len(enc.encode(markdown))
        reduction = round((1 - markdown_tokens / max(original_tokens, 1)) * 100, 1)
        return send_json(start_response, {
            'title': f'YouTube Transcript: {video_id}',
            'markdown': markdown,
            'original_token_count': original_tokens,
            'markdown_token_count': markdown_tokens,
            'reduction_percent': reduction,
        })
    except Exception as e:
        return send_json(start_response, {'error': f'{type(e).__name__}: {e}'})


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('content-length', 0)))
        environ = {
            'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': self.headers.get('content-type', ''),
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': BytesIO(body),
        }
        self._run_wsgi(environ)

    def do_GET(self):
        self._send_json({'error': 'Method not allowed. Use POST.'}, 405)

    def _run_wsgi(self, environ):
        status_headers = {}

        def start_response(status, headers):
            status_headers['status'] = status
            status_headers['headers'] = headers

        chunks = handle_wsgi_request(environ, start_response)
        status = int(status_headers.get('status', '200 OK').split()[0])
        headers = dict(status_headers.get('headers', []))
        body = b''.join(chunks)
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)
