"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type InputMode = "file" | "youtube";

interface ConvertResult {
  filename?: string;
  title?: string;
  markdown: string;
  original_token_count: number;
  markdown_token_count: number;
  reduction_percent: number;
  error?: string;
  image_description_error?: string;
}

const ACCEPT = ".pdf,.docx,.pptx,.xlsx,.csv,.jpg,.jpeg,.png,.webp";

function fmt(n: number) {
  return n.toLocaleString();
}

export default function Home() {
  const [mode, setMode] = useState<InputMode>("file");
  const [file, setFile] = useState<File | null>(null);
  const [ytUrl, setYtUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ConvertResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [dark, setDark] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);

  const toggleDark = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  const selectFile = useCallback((f: File) => {
    setFile(f);
    setResult(null);
    setError(null);
    setCopied(false);
  }, []);

  const convertFile = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    fd.append("file", file);

    try {
      const res = await fetch("/api/convert", { method: "POST", body: fd });
      const data: ConvertResult = await res.json();
      if (data.error) {
        setError(data.error);
        return;
      }
      setResult(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("API error:", e);
      setError(`Network error: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const convertYoutube = async () => {
    if (!ytUrl.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/convert-youtube", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: ytUrl.trim() }),
      });
      const data: ConvertResult = await res.json();
      if (data.error) {
        setError(data.error);
        return;
      }
      setResult(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("API error:", e);
      setError(`Network error: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) selectFile(f);
  };

  const copyMd = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(result.markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadMd = () => {
    if (!result) return;
    const blob = new Blob([result.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const name = result.filename || result.title || "output";
    a.download = name.replace(/\.[^.]+$/, "") + ".md";
    a.click();
    URL.revokeObjectURL(url);
  };

  const reset = () => {
    setResult(null);
    setFile(null);
    setYtUrl("");
    setError(null);
    setCopied(false);
  };

  const inputName = result
    ? result.filename || result.title || "Unknown"
    : "";

  const maxT = result
    ? Math.max(result.original_token_count, result.markdown_token_count, 1)
    : 1;

  return (
    <main className="min-h-screen p-4 md:p-8 max-w-5xl mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold">MD Converter</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1 text-sm">
            Convert files &amp; YouTube URLs to Markdown &middot; Compare token usage
          </p>
        </div>
        <button
          onClick={toggleDark}
          className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          aria-label="Toggle dark mode"
        >
          {dark ? (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
            </svg>
          )}
        </button>
      </header>

      {!result && (
        <>
          <div className="flex gap-1 mb-6 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg w-fit">
            <button
              onClick={() => setMode("file")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "file"
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              Upload File
            </button>
            <button
              onClick={() => setMode("youtube")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                mode === "youtube"
                  ? "bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm"
                  : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
              }`}
            >
              YouTube URL
            </button>
          </div>

          {mode === "file" ? (
            <div
              onDrop={onDrop}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all ${
                dragOver
                  ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                  : "border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 bg-gray-50 dark:bg-gray-900"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) selectFile(f);
                }}
                className="hidden"
              />

              {!file ? (
                <>
                  <svg className="w-12 h-12 mx-auto mb-4 text-gray-400 dark:text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="font-medium text-gray-700 dark:text-gray-300">
                    Drop a file here, or click to browse
                  </p>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                    PDF, DOCX, PPTX, XLSX, CSV, JPG, PNG, WebP &mdash; max 10 MB
                  </p>
                </>
              ) : (
                <div>
                  <p className="font-medium mb-1">{file.name}</p>
                  <p className="text-sm text-gray-400 dark:text-gray-500 mb-4">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  <div className="flex gap-3 justify-center">
                    <button
                      onClick={(e) => { e.stopPropagation(); convertFile(); }}
                      disabled={loading}
                      className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
                    >
                      {loading ? "Converting..." : "Convert to Markdown"}
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setFile(null); }}
                      disabled={loading}
                      className="px-4 py-2 bg-gray-200 dark:bg-gray-700 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
              <label htmlFor="yt-input" className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
                Paste a YouTube URL
              </label>
              <div className="flex gap-3">
                <input
                  id="yt-input"
                  type="text"
                  value={ytUrl}
                  onChange={(e) => setYtUrl(e.target.value)}
                  placeholder="https://youtube.com/watch?v=... or https://youtu.be/..."
                  className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all text-sm"
                  onKeyDown={(e) => { if (e.key === "Enter") convertYoutube(); }}
                />
                <button
                  onClick={convertYoutube}
                  disabled={loading || !ytUrl.trim()}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium text-sm whitespace-nowrap"
                >
                  {loading ? "Converting..." : "Convert"}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {loading && (
        <div className="mt-8 p-8 text-center">
          <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
          <p className="text-gray-500 dark:text-gray-400">Converting...</p>
        </div>
      )}

      {error && (
        <div className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
          {error}
          <button onClick={() => setError(null)} className="ml-2 underline">Dismiss</button>
        </div>
      )}

      {result && (
        <div className="mt-8 space-y-6">
          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
            <h2 className="text-lg font-semibold mb-4">Token Comparison</h2>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-500 dark:text-gray-400">Raw Text</span>
                  <span className="font-mono">{fmt(result.original_token_count)} tokens</span>
                </div>
                <div className="h-4 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full transition-all"
                    style={{ width: `${(result.original_token_count / maxT) * 100}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-gray-500 dark:text-gray-400">Markdown</span>
                  <span className="font-mono">{fmt(result.markdown_token_count)} tokens</span>
                </div>
                <div className="h-4 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-green-500 rounded-full transition-all"
                    style={{ width: `${(result.markdown_token_count / maxT) * 100}%` }}
                  />
                </div>
              </div>
              <div className="pt-3 border-t border-gray-100 dark:border-gray-800 text-center">
                <span className={`text-2xl font-bold ${
                  result.reduction_percent >= 0
                    ? "text-green-600 dark:text-green-400"
                    : "text-orange-500"
                }`}>
                  {result.reduction_percent >= 0 ? "" : "+"}
                  {Math.abs(result.reduction_percent)}%
                  {result.reduction_percent >= 0 ? " smaller" : " larger"}
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
              <span className="font-semibold text-sm truncate mr-4">
                {inputName}
              </span>
              <div className="flex gap-2 items-center shrink-0">
                <button
                  onClick={() => setShowRaw(!showRaw)}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
                >
                  {showRaw ? "Rendered" : "Raw"}
                </button>
                <button
                  onClick={copyMd}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
                <button
                  onClick={downloadMd}
                  className="px-3 py-1.5 text-xs font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                >
                  Download .md
                </button>
              </div>
            </div>
            <div className="p-4 max-h-[600px] overflow-y-auto">
              {showRaw ? (
                <pre className="text-sm font-mono whitespace-pre-wrap break-words">{result.markdown}</pre>
              ) : (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {result.markdown}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>

          {result.image_description_error && (
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-400 text-sm">
              Image description unavailable: {result.image_description_error}
            </div>
          )}

          <div className="text-center">
            <button
              onClick={reset}
              className="px-6 py-2 bg-gray-200 dark:bg-gray-700 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors font-medium"
            >
              Convert Another
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
