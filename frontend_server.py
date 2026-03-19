#!/usr/bin/env python3
"""
RepoSense Frontend Server
Serves a landing page on port 9000, runs RepoSense on a submitted repo URL,
then serves the generated report. Provides a back button to return to landing page.
"""

import html
import os
import re
import subprocess
import sys
import threading
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 9000
REPOSENSE_DIR = Path(__file__).parent
JAR_PATH = REPOSENSE_DIR / "build" / "jar" / "RepoSense.jar"
REPORT_OUTPUT_DIR = REPOSENSE_DIR / "reposense-report"

# ─── Shared state ────────────────────────────────────────────────────────────
state = {
    "status": "idle",   # idle | running | done | error
    "message": "",
    "repo_url": "",
}
state_lock = threading.Lock()


# ─── HTML Templates ──────────────────────────────────────────────────────────

LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>RepoSense Analyzer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:        #0d1117;
      --surface:   #161b22;
      --surface2:  #21262d;
      --border:    #30363d;
      --accent:    #58a6ff;
      --accent2:   #3fb950;
      --text:      #e6edf3;
      --muted:     #7d8590;
      --red:       #f85149;
      --radius:    12px;
    }

    html, body { height: 100%; }

    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }

    /* Background subtle grid */
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(88,166,255,.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(88,166,255,.03) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
    }

    .container {
      width: 100%;
      max-width: 640px;
      display: flex;
      flex-direction: column;
      gap: 32px;
      position: relative;
      z-index: 1;
    }

    /* Header */
    .header { text-align: center; }

    .logo {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
    }

    .logo-icon {
      width: 48px; height: 48px;
      background: linear-gradient(135deg, var(--accent), #a371f7);
      border-radius: 14px;
      display: flex; align-items: center; justify-content: center;
      font-size: 22px;
      box-shadow: 0 0 24px rgba(88,166,255,.35);
    }

    h1 {
      font-size: 2.2rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent) 0%, #a371f7 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.02em;
    }

    .subtitle {
      font-size: 1rem;
      color: var(--muted);
      margin-top: 8px;
      line-height: 1.6;
    }

    /* Card */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 32px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    label {
      display: block;
      font-size: 0.875rem;
      font-weight: 500;
      color: var(--muted);
      margin-bottom: 8px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    .input-wrap { position: relative; }

    .url-icon {
      position: absolute;
      left: 14px; top: 50%;
      transform: translateY(-50%);
      color: var(--muted);
      font-size: 1rem;
      pointer-events: none;
    }

    input[type="url"], input[type="text"] {
      width: 100%;
      padding: 14px 14px 14px 42px;
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-family: inherit;
      font-size: 0.95rem;
      outline: none;
      transition: border-color .2s, box-shadow .2s;
    }

    input[type="url"]:focus, input[type="text"]:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(88,166,255,.15);
    }

    input::placeholder { color: var(--muted); }

    .btn {
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: 8px;
      font-family: inherit;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: all .2s;
      display: flex; align-items: center; justify-content: center; gap: 8px;
    }

    .btn-primary {
      background: linear-gradient(135deg, var(--accent), #a371f7);
      color: #fff;
      box-shadow: 0 4px 16px rgba(88,166,255,.3);
    }

    .btn-primary:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 24px rgba(88,166,255,.45);
    }

    .btn-primary:active { transform: translateY(0); }

    /* Info section */
    .info-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 16px;
      background: var(--surface2);
      border-radius: 8px;
      font-size: 0.85rem;
      color: var(--muted);
    }

    .info-row span { color: var(--text); }

    /* Footer */
    .footer {
      text-align: center;
      font-size: 0.8rem;
      color: var(--muted);
    }

    /* Error banner */
    .error-banner {
      background: rgba(248,81,73,.1);
      border: 1px solid rgba(248,81,73,.4);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 0.875rem;
      color: var(--red);
      display: flex; align-items: flex-start; gap: 8px;
    }

    /* Loading state */
    #loading-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(13,17,23,.85);
      backdrop-filter: blur(8px);
      z-index: 100;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 24px;
    }

    #loading-overlay.active { display: flex; }

    .spinner {
      width: 52px; height: 52px;
      border: 3px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }

    @keyframes spin { to { transform: rotate(360deg); } }

    .loading-text {
      font-size: 1.1rem;
      font-weight: 500;
      color: var(--text);
    }

    .loading-sub {
      font-size: 0.875rem;
      color: var(--muted);
      text-align: center;
      max-width: 320px;
    }

    /* Status dots */
    .dot {
      display: inline-block;
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--accent2);
      margin-right: 6px;
    }
  </style>
</head>
<body>

<div id="loading-overlay">
  <div class="spinner"></div>
  <div class="loading-text">Analyzing repository…</div>
  <div class="loading-sub">Cloning and analyzing commits from the past month. This may take a minute.</div>
</div>

<div class="container">
  <div class="header">
    <div class="logo">
      <div class="logo-icon">📊</div>
      <h1>RepoSense</h1>
    </div>
    <p class="subtitle">Paste a public Git repository URL to generate a<br/>contribution analysis report for the past 30 days.</p>
  </div>

  {ERROR_SECTION}

  <div class="card">
    <form id="analyze-form" action="/analyze" method="POST">
      <div>
        <label for="url-input">Repository URL</label>
        <div class="input-wrap">
          <span class="url-icon">🔗</span>
          <input
            id="url-input"
            type="text"
            name="url"
            required
            placeholder="https://github.com/owner/repo"
            value="{PREFILL_URL}"
            autocomplete="off"
            spellcheck="false"
          />
        </div>
      </div>

      <div class="info-row">
        <span>📅</span>
        <div>Analysis period: <span>last 1 month</span> (up to today)</div>
      </div>

      <button class="btn btn-primary" type="submit">
        <span>🚀</span> Analyze Repository
      </button>
    </form>
  </div>

  <div class="footer">
    <span class="dot"></span> Powered by RepoSense · Contributions from the past 30 days
  </div>
</div>

<script>
  document.getElementById('analyze-form').addEventListener('submit', function() {
    document.getElementById('loading-overlay').classList.add('active');
  });
</script>
</body>
</html>
"""

ANALYZING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta http-equiv="refresh" content="3;url=/status"/>
  <title>Analyzing… – RepoSense</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet"/>
  <style>
    body {
      margin: 0; font-family: 'Inter', sans-serif;
      background: #0d1117; color: #e6edf3;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh;
    }
    .box { text-align: center; }
    .spinner {
      width: 56px; height: 56px;
      border: 3px solid #30363d; border-top-color: #58a6ff;
      border-radius: 50%; animation: spin .8s linear infinite;
      margin: 0 auto 24px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    h2 { font-size: 1.5rem; margin-bottom: 8px; }
    p  { color: #7d8590; font-size: 0.9rem; }
  </style>
</head>
<body>
<div class="box">
  <div class="spinner"></div>
  <h2>Analyzing repository…</h2>
  <p>This page will update automatically.</p>
</div>
</body>
</html>
"""

BACK_BANNER = """
<div id="rs-back-banner" style="
  position: fixed; top: 0; left: 0; right: 0; z-index: 99999;
  background: linear-gradient(90deg, #1c2128, #161b22);
  border-bottom: 1px solid #30363d;
  padding: 10px 20px;
  display: flex; align-items: center; gap: 16px;
  font-family: 'Inter', system-ui, sans-serif;
  font-size: 14px; color: #e6edf3;
">
  <span style="font-size:18px;">📊</span>
  <strong style="color:#58a6ff;">RepoSense</strong>
  <span style="color:#7d8590;">Report for:&nbsp;</span>
  <span style="color:#a371f7; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:400px;">REPO_URL_PLACEHOLDER</span>
  <a href="/exit" style="
    margin-left: auto; padding: 6px 14px;
    background: #21262d; border: 1px solid #30363d;
    border-radius: 6px; color: #e6edf3; text-decoration: none;
    font-weight: 500; transition: background .15s;
  " onmouseover="this.style.background='#30363d'" onmouseout="this.style.background='#21262d'">
    ← Back to Analyzer
  </a>
</div>
<div style="height:49px;"></div>
"""


# ─── Request Handler ──────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Suppress default noisy output
        pass

    # ── Routing ──────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "":
            self._serve_landing()
        elif path == "/status":
            self._serve_status()
        elif path == "/exit":
            self._redirect("/")
        elif path.startswith("/report/") or path == "/report":
            self._serve_report_file(path)
        else:
            self._send_404()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/analyze":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            params = urllib.parse.parse_qs(body)
            url = params.get("url", [""])[0].strip()

            if not url:
                self._serve_landing(error="Please enter a repository URL.")
                return

            with state_lock:
                if state["status"] == "running":
                    self._serve_landing(error="An analysis is already running. Please wait.")
                    return
                state["status"] = "running"
                state["message"] = ""
                state["repo_url"] = url

            # Run RepoSense in a background thread
            t = threading.Thread(target=self._run_reposense, args=(url,), daemon=True)
            t.start()

            # Immediately show the analyzing page (which polls /status)
            self._send_html(ANALYZING_PAGE)
        else:
            self._send_404()

    # ── Page Handlers ─────────────────────────────────────────────────────────

    def _serve_landing(self, error=None, prefill_url=""):
        with state_lock:
            last_url = state.get("repo_url", "")
            last_err = state.get("message", "")
            st = state.get("status", "idle")

        # After a failed run, show the error and reset
        if error is None and st == "error" and last_err:
            error = last_err
            with state_lock:
                state["status"] = "idle"
                state["message"] = ""

        error_html = ""
        if error:
            error_html = f"""
            <div class="error-banner">
              <span>⚠️</span>
              <div>{error}</div>
            </div>
            """

        page = LANDING_PAGE.replace("{ERROR_SECTION}", error_html)
        page = page.replace("{PREFILL_URL}", html.escape(prefill_url or last_url or ""))
        self._send_html(page)

    def _serve_status(self):
        with state_lock:
            st = state["status"]
            msg = state["message"]

        if st == "running":
            # Still running – keep polling
            self._send_html(ANALYZING_PAGE)
        elif st == "done":
            with state_lock:
                state["status"] = "idle"
            self._redirect("/report/")
        elif st == "error":
            self._redirect("/")
        else:
            # idle – go home
            self._redirect("/")

    def _serve_report_file(self, url_path):
        # Strip leading /report
        rel = url_path[len("/report"):]
        if rel == "" or rel == "/":
            rel = "/index.html"

        file_path = REPORT_OUTPUT_DIR / rel.lstrip("/")

        if not file_path.exists():
            self._send_404()
            return

        if file_path.is_dir():
            file_path = file_path / "index.html"
            if not file_path.exists():
                self._send_404()
                return

        content = file_path.read_bytes()
        content_type = self._guess_content_type(file_path.name)

        # Inject back-banner into HTML pages
        if content_type == "text/html" and file_path.name == "index.html":
            with state_lock:
                repo_url = state.get("repo_url", "")
            banner = BACK_BANNER.replace("REPO_URL_PLACEHOLDER", repo_url)
            content_str = content.decode("utf-8", errors="replace")
            # Rewrite absolute asset paths FIRST (before injecting banner,
            # so the banner's own href="/exit" is never touched by the regex)
            content_str = self._rewrite_asset_paths(content_str)
            # Then inject banner right after <body>
            content_str = content_str.replace("<body>", f"<body>\n{banner}", 1)
            content = content_str.encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # ── RepoSense Runner ──────────────────────────────────────────────────────

    def _run_reposense(self, url):
        # Calculate since date (1 month ago)
        since = (datetime.now() - timedelta(days=30)).strftime("%d/%m/%Y")

        cmd = [
            "java", "-jar", str(JAR_PATH),
            "--repos", url,
            "--since", since,
            "--output", str(REPORT_OUTPUT_DIR.parent),
        ]

        print(f"[RepoSense] Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(REPOSENSE_DIR),
                capture_output=True,
                text=True,
                timeout=600,  # 10-minute timeout
            )
            if result.returncode == 0:
                with state_lock:
                    state["status"] = "done"
                    state["message"] = ""
                print("[RepoSense] Analysis complete ✓")
            else:
                err_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error."
                # Extract last meaningful line
                lines = [l.strip() for l in err_msg.splitlines() if l.strip()]
                short = lines[-1] if lines else "RepoSense failed."
                with state_lock:
                    state["status"] = "error"
                    state["message"] = f"Analysis failed: {short}"
                print(f"[RepoSense] Error: {err_msg}")
        except subprocess.TimeoutExpired:
            with state_lock:
                state["status"] = "error"
                state["message"] = "Analysis timed out (10 minutes). The repository may be too large."
            print("[RepoSense] Timeout")
        except Exception as exc:
            with state_lock:
                state["status"] = "error"
                state["message"] = f"Unexpected error: {exc}"
            print(f"[RepoSense] Exception: {exc}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rewrite_asset_paths(self, html: str) -> str:
        """
        The RepoSense report uses absolute paths like src="/..." or href="/..."
        We need these to be relative to /report/ so they resolve correctly.
        Only rewrite paths that start with "/" but not "/report/" already.
        """
        def replace_src(m):
            attr, path = m.group(1), m.group(2)
            if path.startswith("/report/") or path.startswith("http"):
                return m.group(0)
            return f'{attr}="/report{path}"'

        html = re.sub(r'(src|href)="(/[^"]*)"', replace_src, html)
        return html

    def _send_html(self, html: str, status=200):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str, status=302):
        self.send_response(status)
        self.send_header("Location", location)
        self.end_headers()

    def _send_404(self):
        msg = b"404 Not Found"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        ext = Path(filename).suffix.lower()
        return {
            ".html": "text/html",
            ".css":  "text/css",
            ".js":   "application/javascript",
            ".json": "application/json",
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".svg":  "image/svg+xml",
            ".ico":  "image/x-icon",
            ".woff": "font/woff",
            ".woff2":"font/woff2",
            ".ttf":  "font/ttf",
        }.get(ext, "application/octet-stream")


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    if not JAR_PATH.exists():
        print(f"ERROR: RepoSense JAR not found at {JAR_PATH}")
        print("Please build the project first: ./gradlew shadowJar")
        sys.exit(1)

    server = HTTPServer(("", PORT), Handler)
    print(f"✅  RepoSense Analyzer running at http://localhost:{PORT}")
    print("    Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
