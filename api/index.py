import json
import os
import re
import tempfile


ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".csv", ".html", ".htm", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif",
}
MAX_SIZE = 10 * 1024 * 1024


def extract_raw_text(file_path, ext):
    ext = ext.lower()

    if ext == ".pdf":
        import fitz
        doc = fitz.open(file_path)
        texts = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(texts)

    if ext == ".docx":
        import docx
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)

    if ext == ".pptx":
        from pptx import Presentation
        prs = Presentation(file_path)
        texts = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text)
        return "\n".join(texts)

    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        texts = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = " ".join(str(c) for c in row if c is not None)
                if row_text.strip():
                    texts.append(row_text)
        wb.close()
        return "\n".join(texts)

    if ext in (".txt", ".csv", ".html", ".htm"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    return None


def strip_markdown(md):
    text = md
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(\*{1,3}|_{1,3})([^*_]+)\1", r"\2", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```[\w]*\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def app(environ, start_response):
    def send_json(data, status=200):
        status_map = {
            200: "OK", 400: "Bad Request", 405: "Method Not Allowed",
            413: "Request Entity Too Large", 500: "Internal Server Error",
        }
        headers = [
            ("Content-Type", "application/json"),
            ("Access-Control-Allow-Origin", "*"),
        ]
        start_response(f"{status} {status_map.get(status, 'Error')}", headers)
        return [json.dumps(data).encode()]

    if environ["REQUEST_METHOD"] != "POST":
        return send_json({"error": "Method not allowed. Use POST."}, 405)

    cl = environ.get("CONTENT_LENGTH", "0")
    try:
        content_length = int(cl) if cl else 0
    except (ValueError, TypeError):
        content_length = 0

    if content_length > MAX_SIZE:
        return send_json({"error": "File too large. Maximum size is 10MB."}, 413)

    content_type = environ.get("CONTENT_TYPE", "")
    if "multipart/form-data" not in content_type:
        return send_json({"error": "Request must be multipart/form-data"}, 400)

    try:
        from multipart import parse_form_data
        _, files = parse_form_data(environ)
    except ImportError:
        try:
            from multipart.multipart import parse_form_data
            _, files = parse_form_data(environ)
        except ImportError:
            return send_json({"error": "Server configuration error: multipart parser not available"}, 500)
    except Exception as e:
        return send_json({"error": f"Failed to parse upload: {e}"}, 400)

    if "file" not in files:
        return send_json({"error": 'No file uploaded. Use form field name "file".'}, 400)

    uploaded = files["file"]
    filename = uploaded.filename
    if not filename:
        return send_json({"error": "No file selected"}, 400)

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return send_json({
            "error": f'Unsupported file type "{ext}". Supported: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
        }, 400)

    file_bytes = uploaded.file.read()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            from markitdown import MarkItDown
            md_engine = MarkItDown()
            result = md_engine.convert(tmp_path)
            markdown = result.text_content
        except ImportError as e:
            return send_json({"error": f"Missing dependency: {e}"}, 500)
        except Exception as e:
            err = str(e)
            if ext in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif"}:
                return send_json({
                    "error": "Image conversion requires OCR dependencies not available in this serverless environment."
                }, 400)
            return send_json({"error": f"Conversion failed: {err}"}, 500)

        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
        except ImportError as e:
            return send_json({"error": f"Token counting unavailable: {e}"}, 500)

        raw = extract_raw_text(tmp_path, ext)
        if raw is None:
            raw = strip_markdown(markdown)

        if raw.strip():
            original_tokens = len(enc.encode(raw))
        else:
            original_tokens = 0

        markdown_tokens = len(enc.encode(markdown))
        reduction = ((original_tokens - markdown_tokens) / original_tokens * 100) if original_tokens > 0 else 0

        return send_json({
            "filename": filename,
            "markdown": markdown,
            "original_token_count": original_tokens,
            "markdown_token_count": markdown_tokens,
            "reduction_percent": round(reduction, 1),
        })
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
