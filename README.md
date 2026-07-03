# MD Converter

Convert files and YouTube URLs to Markdown with token-count comparison. Built with Next.js 14 (App Router), TypeScript, Tailwind CSS, and Vercel Python serverless functions.

## Dependencies

### Node.js (package.json)

```json
{
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.4.0"
  }
}
```

### Python (requirements.txt)

```
markitdown[pdf,docx,pptx,xlsx]==0.0.1a3
tiktoken==0.7.0
```

**Important:** Use only the extras listed above. Do NOT use `markitdown[all]` — it pulls in OCR dependencies (easyocr, pytesseract, torch) that exceed Vercel's 250 MB function size limit.

## Local Development

```bash
# Install Node.js dependencies
npm install

# Install Python dependencies
pip install -r requirements.txt

# Run local dev server (tests both Python functions + Next.js together)
vercel dev

# Verify production build succeeds before deploying
npm run build
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_API_KEY` | For images | Get a free key at [build.nvidia.com](https://build.nvidia.com) (1,000 inference credits, no credit card required). Must be set in Vercel Project Settings > Environment Variables before deploying. |

Without `NVIDIA_API_KEY`, image uploads will still convert (MarkItDown handles metadata extraction) but the vision description will be skipped. The response will include `"image_description_error": "NVIDIA_API_KEY not set"`.

## Deployment

1. Push to a Git repository connected to Vercel, or drag-and-drop the project folder to [vercel.com/new](https://vercel.com/new).
2. Set `NVIDIA_API_KEY` in Project Settings > Environment Variables (optional — only needed for image descriptions).
3. Vercel auto-detects Next.js + Python from `requirements.txt`.
4. Deploy.

### Vercel Plan Notes

This project intentionally omits `vercel.json` while stabilizing routing. On the Hobby (free) plan, Python function timeout is capped at 10 seconds. Large PDFs or slow NVIDIA API calls may time out.

## Input Support

| Input Type | Works | Known Limitations |
|------------|-------|-------------------|
| PDF (.pdf) | Yes | Scanned/image-only PDFs require OCR (tesseract) which is not available in this serverless environment. Only text-layer PDFs extract properly. |
| DOCX (.docx) | Yes | Legacy `.doc` (pre-OOXML) format is NOT supported — it requires LibreOffice, unavailable here. |
| PPTX (.pptx) | Yes | Legacy `.ppt` format is NOT supported. |
| XLSX (.xlsx) | Yes | Legacy `.xls` format is NOT supported. |
| CSV (.csv) | Yes | |
| Images (jpg/png/webp) | Yes | MarkItDown extracts EXIF/metadata only. For content descriptions, the NVIDIA vision API is called (requires `NVIDIA_API_KEY`). Without the key, metadata-only output is returned. |
| YouTube URLs | Yes | Requires the video to have captions enabled. Transcripts are grouped into paragraphs (~45s intervals). |

## Architecture

```
/                     Next.js App Router (app/page.tsx)
├── app/
│   ├── page.tsx      Frontend — file upload, YouTube URL input, markdown preview, token comparison
│   ├── layout.tsx    Root layout with dark mode FOUC prevention
│   └── globals.css   Tailwind directives
├── api/
│   ├── convert.py          Python — file upload conversion route
│   └── convert-youtube.py  Python — YouTube transcript route
├── requirements.txt
├── package.json
└── next.config.mjs
```

### API Endpoints

- **`POST /api/convert`** — Upload a file via `multipart/form-data` with field name `file`. Returns JSON with markdown text and token counts.
- **`POST /api/convert-youtube`** — Send `{"url": "..."}` as JSON body. Returns JSON with formatted transcript and token counts.

Both endpoints use Vercel's Python `BaseHTTPRequestHandler` convention directly. No rewrite layer is required.

Both endpoints return `{"error": "..."}` on failure (always HTTP 200).

### Token Counting

Uses `tiktoken` with the `cl100k_base` encoding (the same tokenizer used by GPT-4). The raw text token count is computed from:
1. A per-format raw text extractor (PyMuPDF for PDF, python-docx for DOCX, etc.) — when available.
2. A markdown-stripping fallback for formats where raw extraction is not feasible.

The reduction percentage shows how much smaller the markdown representation is compared to the raw text.

### NVIDIA Vision Model

Image description uses `meta/llama-3.2-90b-vision-instruct` via NVIDIA's API. **Verify the exact model ID at [build.nvidia.com/models](https://build.nvidia.com/models) before relying on this** — NVIDIA periodically renames/updates their model catalog. Update the model ID in `api/convert.py:describe_image()` accordingly.

## Known Limitations

1. **Scanned PDFs** — Image-only PDFs need OCR (tesseract). This app only extracts text from text-layer PDFs.
2. **Legacy Office formats** — `.doc`, `.ppt`, `.xls` (pre-OOXML) require LibreOffice, which is not available on Vercel serverless. Only modern `.docx`, `.pptx`, `.xlsx` are supported.
3. **Vercel Hobby timeout** — The free plan caps function execution at 10 seconds. Large PDFs or slow NVIDIA API calls may time out.
4. **YouTube without captions** — Only videos with captions enabled can be transcribed. Autogenerated captions count if the video has them.
