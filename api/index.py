import json
import os
import re
import tempfile
import uuid


ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx",
    ".csv", ".html", ".htm", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif",
}
MAX_SIZE = 10 * 1024 * 1024


def parse_multipart(environ):
    content_type = environ.get("CONTENT_TYPE", "")
    content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)

    if content_length > MAX_SIZE:
        return None, "File too large. Maximum size is 10MB."

    if "multipart/form-data" not in content_type:
        return None, "Request must be multipart/form-data"

    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part[9:].strip('"').strip("'")
            break

    if not boundary:
        return None, "No boundary found in Content-Type"

    body = environ["wsgi.input"].read(content_length)
    boundary_bytes = boundary.encode("utf-8")

    parts = body.split(b"--" + boundary_bytes)
    if not parts:
        return None, "No multipart parts found"

    filename = None
    file_content = None

    for part in parts:
        if part == b"" or part == b"--\r\n" or part == b"--\n":
            continue
        if part.strip() == b"--":
            break

        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            header_end = part.find(b"\n\n")
        if header_end == -1:
            continue

        headers_raw = part[:header_end].decode("utf-8", errors="replace")
        data = part[header_end:]
        if data.startswith(b"\r\n"):
            data = data[2:]
        elif data.startswith(b"\n"):
            data = data[1:]
        if data.endswith(b"\r\n"):
            data = data[:-2]
        elif data.endswith(b"\n"):
            data = data[:-1]

        if 'name="file"' not in headers_raw and "name='file'" not in headers_raw:
            continue

        fname_match = re.search(r'filename="([^"]*)"', headers_raw)
        if not fname_match:
            fname_match = re.search(r"filename='([^']*)'", headers_raw)
        if not fname_match:
            continue

        filename = os.path.basename(fname_match.group(1))
        file_content = data
        break

    if not filename or file_content is None:
        return None, 'No file found. Use form field name "file".'

    return (filename, file_content), None


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

    try:
        if environ["REQUEST_METHOD"] != "POST":
            return send_json({"error": "Method not allowed. Use POST."}, 405)

        result, err = parse_multipart(environ)
        if err:
            if "too large" in err.lower():
                return send_json({"error": err}, 413)
            return send_json({"error": err}, 400)

        filename, file_bytes = result

        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return send_json({
                "error": f'Unsupported file type "{ext}". Supported: {", ".join(sorted(ALLOWED_EXTENSIONS))}'
            }, 400)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                from markitdown import MarkItDown
                md_engine = MarkItDown()
                result_obj = md_engine.convert(tmp_path)
                markdown = result_obj.text_content
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
            except Exception as e:
                return send_json({"error": f"Token counting unavailable: {e}"}, 500)

            raw = extract_raw_text(tmp_path, ext)
            if raw is None:
                raw = strip_markdown(markdown)

            original_tokens = len(enc.encode(raw)) if raw.strip() else 0
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
    except Exception as e:
        return send_json({"error": f"Internal error: {e}"}, 500)
