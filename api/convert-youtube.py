import json
import os
import re
import urllib.parse


def extract_video_id(url):
    parsed = urllib.parse.urlparse(url.strip())

    if parsed.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed.path == '/watch':
            qs = urllib.parse.parse_qs(parsed.query)
            v = qs.get('v', [None])[0]
            if v:
                return v
        m = re.match(r'^/shorts/([a-zA-Z0-9_-]{11})', parsed.path)
        if m:
            return m.group(1)

    if parsed.hostname == 'youtu.be':
        path = parsed.path.lstrip('/')
        if path:
            return path[:11]

    return None


def group_transcript(transcript, group_seconds=45):
    if not transcript:
        return ''

    paragraphs = []
    current = []
    current_start = transcript[0].get('start', 0)

    for entry in transcript:
        text = entry.get('text', '').strip()
        if not text:
            continue
        start = entry.get('start', 0)

        if start - current_start >= group_seconds and current:
            paragraphs.append(' '.join(current))
            current = []
            current_start = start

        current.append(text)

    if current:
        paragraphs.append(' '.join(current))

    return '\n\n'.join(paragraphs)


def app(environ, start_response):
    def send(data, status=200):
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

    try:
        if environ['REQUEST_METHOD'] != 'POST':
            return send({'error': 'Method not allowed. Use POST.'})

        content_length = int(environ.get('CONTENT_LENGTH', 0) or 0)
        body = environ['wsgi.input'].read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            return send({'error': f'{type(e).__name__}: {e}'})

        url = (data.get('url') or '').strip()
        if not url:
            return send({'error': 'No URL provided'})

        video_id = extract_video_id(url)
        if not video_id:
            return send({'error': 'Could not extract a valid video ID from this URL'})

        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            err_cls = type(e).__name__
            err_msg = str(e)
            if 'TranscriptsDisabled' in err_cls or 'TranscriptsDisabled' in err_msg:
                return send({'error': 'This video has captions disabled'})
            if 'NoTranscriptFound' in err_cls or 'No transcript found' in err_msg:
                return send({'error': 'No transcript available for this video'})
            if 'VideoUnavailable' in err_cls or 'Video unavailable' in err_msg:
                return send({'error': 'This video is private or unavailable'})
            return send({'error': f'{err_cls}: {err_msg}'})

        raw_text = '\n'.join(e.get('text', '') for e in transcript if e.get('text'))
        formatted = group_transcript(transcript)
        markdown = f'# YouTube Transcript\n\n{formatted}\n\n---\n*Source: {url}*'

        try:
            import tiktoken
            enc = tiktoken.get_encoding('cl100k_base')
        except Exception as e:
            return send({'error': f'{type(e).__name__}: {e}'})

        original_tokens = len(enc.encode(raw_text)) if raw_text.strip() else 0
        markdown_tokens = len(enc.encode(markdown))
        reduction = round((1 - markdown_tokens / max(original_tokens, 1)) * 100, 1)

        return send({
            'title': f'YouTube Transcript: {video_id}',
            'markdown': markdown,
            'original_token_count': original_tokens,
            'markdown_token_count': markdown_tokens,
            'reduction_percent': reduction,
        })

    except Exception as e:
        return send({'error': f'{type(e).__name__}: {e}'})
