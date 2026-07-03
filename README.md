# MD Converter

Convert uploaded files (PDF, DOCX, PPTX, XLSX, CSV, HTML, TXT, images) into
clean Markdown, with a token-count comparison showing how much the conversion
reduces token usage.

Built with **Next.js 14** (App Router, TypeScript, Tailwind) + a **Vercel
Python serverless function** using MarkItDown and tiktoken.

## Project Structure

```
├── app/
│   ├── globals.css        # Tailwind base styles
│   ├── layout.tsx         # Root layout + dark mode script
│   └── page.tsx           # Main page (upload, preview, token comparison)
├── api/
│   └── convert.py         # Vercel Python serverless function
├── public/                # Static assets (empty)
├── package.json
├── requirements.txt       # Python dependencies
├── next.config.mjs
├── tailwind.config.ts
├── postcss.config.mjs
├── tsconfig.json
├── vercel.json            # Vercel deployment config
└── README.md
```

## How to Build and Run Locally

### 1. Install Node dependencies

```bash
npm install
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The Python function is only needed at `/api/convert`. To test the
> full stack locally you need the **Vercel CLI** (`vercel dev`). See step 4.

### 3. Run Next.js dev server (frontend only)

```bash
npm run dev
```

This starts Next.js on `http://localhost:3000`. The `/api/convert` endpoint
will **not** work without the Vercel CLI.

### 4. Run full stack with Vercel CLI (recommended for local testing)

```bash
# Install the Vercel CLI if you haven't already
npm i -g vercel

# Link the project (first time only)
vercel link

# Start the dev server — serves both Next.js frontend and Python function
vercel dev
```

`vercel dev` serves the Next.js frontend AND the Python serverless function
at `/api/convert`.

### 5. Production build

```bash
npm run build
```

Verify the build succeeds before deploying.

## Deploying to Vercel

**Drag-and-drop** this folder into the Vercel dashboard, or run:

```bash
vercel --prod
```

Vercel auto-detects the Next.js framework and the Python serverless function.
No manual configuration needed beyond the `vercel.json` already included.

## Notes on Vercel Python Runtime

| Concern | Status |
|---|---|
| **PDF conversion** | Uses PyMuPDF (pure Python) — works on Vercel |
| **DOCX/PPTX/XLSX** | Uses python-docx / python-pptx / openpyxl — pure Python, works on Vercel |
| **HTML/TXT/CSV** | Built-in text processing — works on Vercel |
| **Images (OCR)** | ❌ **Not supported.** OCR requires `easyocr` + `torch`, which exceed Vercel's 50 MB function size limit |
| **Max file size** | Enforced at 10 MB |
| **Function timeout** | `maxDuration` set to 60 s in `vercel.json` (Pro plan). Free tier caps at 10 s — large/ complex files may time out |

## Requirements Fulfilled

- [x] Drag-and-drop + click-to-upload file input
- [x] Markdown preview with syntax-highlighted code blocks
- [x] Copy to clipboard & Download .md button
- [x] Token count bar chart with % reduction
- [x] Dark mode toggle
- [x] Clean Tailwind UI
- [x] Python serverless function on Vercel
- [x] 10 MB file size limit
- [x] Graceful error handling for unsupported / failed conversions
- [x] Pinned dependencies in `requirements.txt`
# file2md
