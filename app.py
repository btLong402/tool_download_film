"""Video Downloader — GUI App (pywebview).

Hỗ trợ tải video từ mọi trang web: rophim, YouTube, Facebook, TikTok, ...
Nhập nhiều link, tải lần lượt. Chọn folder lưu.
"""

import os
import re
import sys
import threading

import webview  # type: ignore[import-untyped]

from rophim_downloader import download_single_url


def _get_default_save_dir() -> str:
    """Thư mục lưu mặc định, tương thích cross-platform."""
    if sys.platform == "win32":
        # Windows: dùng Downloads hoặc Desktop
        import pathlib
        return str(pathlib.Path.home() / "Downloads")
    return os.path.expanduser("~/Downloads")


DEFAULT_SAVE_DIR = _get_default_save_dir()

HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Video Downloader</title>
<style>
  :root {
    --bg: #1e1e2e; --surface: #313244; --overlay: #45475a;
    --text: #cdd6f4; --dim: #6c7086; --accent: #89b4fa;
    --success: #a6e3a1; --error: #f38ba8; --warn: #fab387;
    --radius: 10px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text);
    padding: 24px; height: 100vh; display: flex; flex-direction: column;
    user-select: none; -webkit-user-select: none;
  }
  h1 { font-size: 22px; font-weight: 700; margin-bottom: 2px; }
  .subtitle { color: var(--dim); font-size: 13px; margin-bottom: 18px; }

  label { font-weight: 600; font-size: 14px; display: block; margin-bottom: 6px; }

  textarea {
    width: 100%; height: 120px; resize: vertical;
    background: var(--surface); color: var(--text); border: 1px solid var(--overlay);
    border-radius: var(--radius); padding: 12px; font-size: 13px;
    font-family: 'SF Mono', 'Fira Code', monospace;
    outline: none; transition: border-color 0.2s;
  }
  textarea:focus { border-color: var(--accent); }
  textarea::placeholder { color: var(--dim); }
  textarea:disabled { opacity: 0.5; }

  .folder-row {
    display: flex; align-items: center; gap: 10px;
    margin: 14px 0;
  }
  .folder-path {
    flex: 1; font-size: 13px; color: var(--accent);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  button {
    font-family: inherit; font-size: 13px; font-weight: 600;
    border: none; border-radius: var(--radius); cursor: pointer;
    padding: 8px 18px; transition: all 0.15s;
    display: inline-flex; align-items: center; gap: 6px;
  }
  button:active { transform: scale(0.97); }
  button:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

  .btn-primary { background: var(--accent); color: var(--bg); }
  .btn-primary:hover:not(:disabled) { filter: brightness(1.1); }
  .btn-stop { background: var(--overlay); color: var(--text); }
  .btn-stop:hover:not(:disabled) { background: var(--error); color: var(--bg); }
  .btn-ghost { background: transparent; color: var(--dim); }
  .btn-ghost:hover:not(:disabled) { color: var(--text); background: var(--surface); }
  .btn-folder { background: var(--surface); color: var(--text); }
  .btn-folder:hover { background: var(--overlay); }

  .btn-row { display: flex; gap: 10px; align-items: center; }
  .btn-row .spacer { flex: 1; }

  .progress-section { margin: 14px 0 0 0; }
  .status {
    font-size: 13px; color: var(--dim); margin-bottom: 6px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .progress-bar {
    width: 100%; height: 6px; background: var(--surface);
    border-radius: 3px; overflow: hidden;
  }
  .progress-fill {
    height: 100%; width: 0%; background: var(--accent);
    border-radius: 3px; transition: width 0.3s;
  }

  .log-section { flex: 1; display: flex; flex-direction: column; margin-top: 14px; min-height: 0; }
  .log-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
  .log-box {
    flex: 1; background: var(--surface); border: 1px solid var(--overlay);
    border-radius: var(--radius); padding: 10px 12px;
    font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px;
    line-height: 1.6; overflow-y: auto; min-height: 0;
    color: var(--text);
  }
  .log-box .success { color: var(--success); }
  .log-box .error { color: var(--error); }
  .log-box .warn { color: var(--warn); }
  .log-box .info { color: var(--accent); }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--overlay); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--dim); }
</style>
</head>
<body>

<h1>🎬 Video Downloader</h1>
<p class="subtitle">Hỗ trợ 1800+ trang web — Paste link, chọn folder, tải!</p>

<label for="links">Danh sách link (mỗi dòng 1 link):</label>
<textarea id="links" placeholder="Paste link vào đây, mỗi dòng 1 link...&#10;&#10;Ví dụ:&#10;https://www.youtube.com/watch?v=...&#10;https://rophim.net/phim/...&#10;https://vimeo.com/..."></textarea>

<div class="folder-row">
  <label style="margin:0">Lưu vào:</label>
  <span class="folder-path" id="folderPath"></span>
  <button class="btn-folder" onclick="chooseFolder()">📁 Chọn folder</button>
</div>

<div class="btn-row">
  <button class="btn-primary" id="btnStart" onclick="startDownload()">▶ Bắt đầu tải</button>
  <button class="btn-stop" id="btnStop" onclick="stopDownload()" disabled>⏹ Dừng</button>
  <span class="spacer"></span>
  <button class="btn-ghost" onclick="clearLog()">🗑 Xoá log</button>
</div>

<div class="progress-section">
  <div class="status" id="status">Sẵn sàng</div>
  <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
</div>

<div class="log-section">
  <div class="log-header">
    <label style="margin:0">Log</label>
  </div>
  <div class="log-box" id="logBox"></div>
</div>

<script>
  const logBox = document.getElementById('logBox');
  const status = document.getElementById('status');
  const progressFill = document.getElementById('progressFill');
  const btnStart = document.getElementById('btnStart');
  const btnStop = document.getElementById('btnStop');
  const linksArea = document.getElementById('links');
  const folderPath = document.getElementById('folderPath');

  // Init folder path
  window.addEventListener('pywebviewready', () => {
    pywebview.api.get_save_dir().then(dir => { folderPath.textContent = dir; });
  });

  function appendLog(msg, cls) {
    const line = document.createElement('div');
    if (cls) line.className = cls;
    line.textContent = msg;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;
  }

  function clearLog() {
    logBox.innerHTML = '';
  }

  function setProgress(pct) {
    progressFill.style.width = pct + '%';
  }

  function setStatus(text, color) {
    status.textContent = text;
    status.style.color = color || 'var(--dim)';
  }

  function setUIDownloading(active) {
    btnStart.disabled = active;
    btnStop.disabled = !active;
    linksArea.disabled = active;
  }

  async function chooseFolder() {
    const dir = await pywebview.api.choose_folder();
    if (dir) folderPath.textContent = dir;
  }

  async function startDownload() {
    const text = linksArea.value.trim();
    if (!text) { alert('Hãy paste ít nhất 1 link video.'); return; }

    const links = text.split('\\n').map(l => l.trim()).filter(l => l.startsWith('http'));
    if (links.length === 0) { alert('Không tìm thấy link hợp lệ (http/https).'); return; }

    setUIDownloading(true);
    setProgress(0);
    await pywebview.api.start_download(links);
  }

  async function stopDownload() {
    await pywebview.api.stop_download();
  }

  // Poll for updates from Python backend
  let pollTimer = null;
  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(async () => {
      const updates = await pywebview.api.poll_updates();
      if (!updates) return;
      for (const u of updates) {
        if (u.type === 'log') appendLog(u.msg, u.cls || '');
        else if (u.type === 'status') setStatus(u.text, u.color);
        else if (u.type === 'progress') setProgress(u.value);
        else if (u.type === 'ui') setUIDownloading(u.active);
      }
    }, 150);
  }
  window.addEventListener('pywebviewready', startPolling);
</script>

</body>
</html>
"""


class Api:
    """Python backend exposed to JS via pywebview."""

    def __init__(self) -> None:
        self._save_dir = DEFAULT_SAVE_DIR
        self._stop_flag = False
        self._downloading = False
        self._updates: list[dict[str, object]] = []
        self._lock = threading.Lock()

    # ── Queue updates for JS polling ────────────────────────────
    def _push(self, update: dict[str, object]) -> None:
        with self._lock:
            self._updates.append(update)

    def poll_updates(self) -> list[dict[str, object]]:
        with self._lock:
            batch = self._updates[:]
            self._updates.clear()
        return batch

    # ── Exposed to JS ──────────────────────────────────────────
    def get_save_dir(self) -> str:
        return self._save_dir

    def choose_folder(self) -> str | None:
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            self._save_dir = result[0]
            return self._save_dir
        return None

    def stop_download(self) -> None:
        self._stop_flag = True
        self._push({"type": "status", "text": "Đang dừng sau video hiện tại...",
                     "color": "var(--warn)"})

    def start_download(self, links: list[str]) -> None:
        if self._downloading:
            return
        self._stop_flag = False
        self._downloading = True
        thread = threading.Thread(
            target=self._download_worker, args=(links,), daemon=True
        )
        thread.start()

    # ── Helpers ─────────────────────────────────────────────────
    def _log(self, msg: str, cls: str = "") -> None:
        self._push({"type": "log", "msg": msg, "cls": cls})

    def _set_status(self, text: str, color: str = "var(--dim)") -> None:
        self._push({"type": "status", "text": text, "color": color})

    def _set_progress(self, value: float) -> None:
        self._push({"type": "progress", "value": value})

    def _set_ui(self, active: bool) -> None:
        self._push({"type": "ui", "active": active})

    def _make_filename(self, url: str, index: int) -> str:
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", url.split("?")[0].rstrip("/"))
        slug = cleaned.rsplit("/", 1)[-1] if "/" in cleaned else f"video_{index + 1}"
        slug = slug[:80]
        if not slug or slug == "_":
            slug = f"video_{index + 1}"
        if not slug.endswith(".mp4"):
            slug += ".mp4"
        return slug

    def _progress_callback(self, done: int, total: int) -> None:
        pct = done / total * 100 if total else 0
        self._set_progress(pct)
        self._set_status(f"Đang tải segments: {done}/{total} ({pct:.0f}%)",
                         "var(--accent)")

    # ── Download worker ─────────────────────────────────────────
    def _download_worker(self, links: list[str]) -> None:
        total = len(links)
        success = 0
        failed = 0

        self._log(f"═══ Bắt đầu tải {total} video ═══", "info")

        for i, url in enumerate(links):
            if self._stop_flag:
                self._log(f"⏹ Đã dừng tại video {i + 1}/{total}.", "warn")
                break

            filename = self._make_filename(url, i)
            output = os.path.join(self._save_dir, filename)

            self._set_status(f"[{i + 1}/{total}] Đang tải...", "var(--accent)")
            self._set_progress(0)
            self._log(f"\n── Video {i + 1}/{total} ──", "info")
            self._log(f"URL: {url}")
            self._log(f"Save: {output}")

            try:
                download_single_url(
                    url, output,
                    log=self._log,
                    progress_callback=self._progress_callback,
                )
                success += 1
                self._log(f"✅ Hoàn thành: {filename}", "success")
            except (ValueError, RuntimeError, FileNotFoundError) as e:
                failed += 1
                self._log(f"❌ Lỗi: {e}", "error")
            except Exception as e:
                failed += 1
                self._log(f"❌ Lỗi không xác định: {e}", "error")

        self._set_progress(100)
        tag = "success" if failed == 0 else "warn"
        self._log(f"\n═══ Xong: {success} thành công, {failed} lỗi / {total} video ═══", tag)
        color = "var(--success)" if failed == 0 else "var(--warn)"
        self._set_status(f"Hoàn tất: {success}/{total} thành công", color)
        self._set_ui(False)
        self._downloading = False


def main() -> None:
    api = Api()
    _window = webview.create_window(
        APP_TITLE,
        html=HTML,
        js_api=api,
        width=800,
        height=650,
        min_size=(600, 500),
    )
    webview.start(debug=False)


APP_TITLE = "Video Downloader"

if __name__ == "__main__":
    main()
