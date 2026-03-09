"""Video Downloader — GUI App (pywebview).

Hỗ trợ tải video từ mọi trang web: rophim, YouTube, Facebook, TikTok, ...
Nhập nhiều link, tải lần lượt. Chọn folder lưu.
"""

import os
import re
import subprocess
import sys
import threading

import webview  # type: ignore[import-untyped]

from dep_check import check_deps, install_ffmpeg, install_missing_packages
from rophim_downloader import download_single_url


def _get_default_save_dir() -> str:
    """Thư mục lưu mặc định, tương thích cross-platform."""
    if sys.platform == "win32":
        # Windows: dùng Downloads hoặc Desktop
        import pathlib
        return str(pathlib.Path.home() / "Downloads")
    return os.path.expanduser("~/Downloads")


DEFAULT_SAVE_DIR = _get_default_save_dir()

# ── Setup Screen HTML ──────────────────────────────────────────
SETUP_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Video Downloader - Setup</title>
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
    display: flex; align-items: center; justify-content: center;
    height: 100vh; padding: 40px;
    user-select: none; -webkit-user-select: none;
  }
  .setup-box {
    background: var(--surface); border-radius: 16px;
    padding: 36px 40px; max-width: 500px; width: 100%;
    text-align: center;
  }
  h1 { font-size: 24px; margin-bottom: 8px; }
  .subtitle { color: var(--dim); font-size: 14px; margin-bottom: 24px; }
  .status-icon { font-size: 48px; margin-bottom: 16px; }
  .dep-list {
    text-align: left; margin: 16px 0; padding: 16px;
    background: var(--bg); border-radius: var(--radius);
  }
  .dep-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 0; font-size: 14px;
  }
  .dep-item .icon { font-size: 18px; width: 24px; text-align: center; }
  .dep-item .name { flex: 1; }
  .dep-item .tag {
    font-size: 11px; padding: 2px 8px; border-radius: 4px;
    font-weight: 600;
  }
  .tag-ok { background: #a6e3a133; color: var(--success); }
  .tag-miss { background: #f38ba833; color: var(--error); }
  .tag-bundle { background: #fab38733; color: var(--warn); }
  .msg { color: var(--dim); font-size: 13px; margin: 16px 0; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
  .msg.installing { color: var(--accent); }
  .msg.error { color: var(--error); }
  .msg.ok { color: var(--success); }
  button {
    font-family: inherit; font-size: 14px; font-weight: 600;
    border: none; border-radius: var(--radius); cursor: pointer;
    padding: 12px 28px; margin: 6px; transition: all 0.15s;
  }
  button:active { transform: scale(0.97); }
  button:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
  .btn-install { background: var(--accent); color: var(--bg); }
  .btn-install:hover:not(:disabled) { filter: brightness(1.1); }
  .btn-skip { background: var(--overlay); color: var(--text); }
  .btn-skip:hover:not(:disabled) { background: var(--dim); }
  .spinner {
    display: inline-block; width: 20px; height: 20px;
    border: 3px solid var(--overlay); border-top-color: var(--accent);
    border-radius: 50%; animation: spin 0.8s linear infinite;
    vertical-align: middle; margin-right: 8px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .update-box {
    text-align: left; margin: 12px 0; padding: 14px 16px;
    background: var(--bg); border-radius: var(--radius);
    border-left: 3px solid var(--accent);
  }
  .update-version { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  .update-notes {
    font-size: 12px; color: var(--dim); max-height: 72px;
    overflow-y: auto; margin-top: 6px; white-space: pre-wrap;
  }
</style>
</head>
<body>
<div class="setup-box">
  <div class="status-icon" id="statusIcon">⚙️</div>
  <h1>Kiểm tra hệ thống</h1>
  <p class="subtitle">Đang kiểm tra các thành phần cần thiết...</p>

  <div class="dep-list" id="depList"></div>
  <div class="update-box" id="updateBox" style="display:none"></div>

  <div class="msg" id="msgBox"></div>

  <div id="btnBox" style="display:none">
    <button class="btn-install" id="btnInstall">📦 Cài đặt</button>
    <button class="btn-skip" id="btnSkip">Bỏ qua</button>
  </div>
</div>

<script>
  const depList = document.getElementById('depList');
  const msgBox = document.getElementById('msgBox');
  const btnBox = document.getElementById('btnBox');
  const btnInstall = document.getElementById('btnInstall');
  const btnSkip = document.getElementById('btnSkip');
  const statusIcon = document.getElementById('statusIcon');
  const updateBox = document.getElementById('updateBox');

  btnInstall.onclick = doInstall;
  btnSkip.onclick = doSkip;

  function renderDeps(deps) {
    depList.innerHTML = '';
    for (const d of deps) {
      const item = document.createElement('div');
      item.className = 'dep-item';
      let icon, tagText, tagClass;
      if (d.status === 'ok') { icon = '✅'; tagText = 'OK'; tagClass = 'tag-ok'; }
      else if (d.status === 'bundled') { icon = '📦'; tagText = 'Bundled'; tagClass = 'tag-bundle'; }
      else { icon = '❌'; tagText = 'Thiếu'; tagClass = 'tag-miss'; }
      item.innerHTML = '<span class="icon">' + icon + '</span>'
        + '<span class="name">' + d.name + (d.note ? ' <small style="color:var(--dim)">(' + d.note + ')</small>' : '') + '</span>'
        + '<span class="tag ' + tagClass + '">' + tagText + '</span>';
      depList.appendChild(item);
    }
  }

  function setMsg(text, cls) {
    msgBox.textContent = text;
    msgBox.className = 'msg' + (cls ? ' ' + cls : '');
  }

  let missingItems = [];
  let canWork = false;

  window.addEventListener('pywebviewready', async () => {
    const result = await pywebview.api.run_check();
    renderDeps(result.deps);
    missingItems = result.missing || [];

    if (result.all_ok) {
      statusIcon.textContent = '✅';
      setMsg('Hệ thống sẵn sàng. Đang kiểm tra cập nhật...', 'ok');
      canWork = true;
      await startUpdateCheck();
    } else if (result.can_work) {
      statusIcon.textContent = '⚠️';
      const names = missingItems.length > 0 ? missingItems.join(', ') : 'ffmpeg (system)';
      setMsg('Khuyến nghị cài: ' + names + ' để đạt chất lượng tốt nhất.\\nHoặc bỏ qua để dùng phiên bản tích hợp.', '');
      btnInstall.textContent = '📦 Cài đặt ' + (missingItems.length > 0 ? '(' + missingItems.length + ')' : '');
      // Nếu chỉ thiếu system ffmpeg
      if (missingItems.length === 0 && !result.has_system_ffmpeg) {
        missingItems = ['ffmpeg'];
        btnInstall.textContent = '📦 Cài ffmpeg hệ thống';
      }
      btnBox.style.display = 'block';
    } else {
      statusIcon.textContent = '❌';
      const names = missingItems.join(', ');
      setMsg('Thiếu các thành phần bắt buộc: ' + names, 'error');
      btnInstall.textContent = '📦 Cài đặt (' + missingItems.length + ')';
      btnBox.style.display = 'block';
      btnSkip.style.display = 'none';
    }
  });

  // ── Kiểm tra cập nhật ────────────────────────────────────────
  async function startUpdateCheck() {
    updateBox.style.display = 'none';
    await pywebview.api.start_update_check();
    const pollUpdate = setInterval(async () => {
      const u = await pywebview.api.poll_update_check();
      if (u === null || u === undefined) return;
      clearInterval(pollUpdate);
      if (u.available) {
        showUpdatePanel(u);
      } else {
        statusIcon.textContent = '✅';
        setMsg('Hệ thống sẵn sàng, đang vào ứng dụng...', 'ok');
        setTimeout(() => pywebview.api.proceed(), 1200);
      }
    }, 500);
  }

  function showUpdatePanel(info) {
    statusIcon.textContent = '🆕';
    updateBox.innerHTML =
      '<div class="update-version">Phiên bản mới: <span style="color:var(--accent)">v' + info.latest + '</span>'
      + ' <small style="color:var(--dim);font-weight:400">(hiện tại: v' + info.current + ')</small></div>'
      + (info.notes ? '<div class="update-notes">' + info.notes + '</div>' : '');
    updateBox.style.display = 'block';
    setMsg('Có bản cập nhật mới!', '');
    btnInstall.textContent = '⬆ Cập nhật ngay';
    btnInstall.onclick = () => doUpdate(info.download_url, info.release_url);
    btnInstall.disabled = false;
    btnSkip.style.display = 'inline-block';
    btnSkip.textContent = 'Bỏ qua';
    btnSkip.onclick = () => pywebview.api.proceed();
    btnBox.style.display = 'block';
  }

  async function doUpdate(downloadUrl, releaseUrl) {
    btnInstall.disabled = true;
    btnSkip.style.display = 'none';
    statusIcon.textContent = '⏳';
    msgBox.innerHTML = '<div class="spinner" style="display:inline-block"></div> Đang tải bản cập nhật...';
    msgBox.className = 'msg installing';
    startPollInstall();
    await pywebview.api.do_download_install(downloadUrl, releaseUrl);
  }

  // ── Cài đặt deps ─────────────────────────────────────────────
  let pollTimer = null;
  function startPollInstall() {
    pollTimer = setInterval(async () => {
      const u = await pywebview.api.poll_install();
      if (!u) return;
      if (u.status === 'installing') {
        setMsg(u.msg, 'installing');
      } else if (u.status === 'ready') {
        clearInterval(pollTimer);
        setMsg(u.msg || 'Đang mở cài đặt...', 'ok');
        await pywebview.api.install_now(u.path);
      } else if (u.status === 'done') {
        clearInterval(pollTimer);
        statusIcon.textContent = '✅';
        setMsg(u.msg, 'ok');
        const result = await pywebview.api.run_check();
        renderDeps(result.deps);
        setTimeout(() => startUpdateCheck(), 1200);
      } else if (u.status === 'error') {
        clearInterval(pollTimer);
        statusIcon.textContent = '❌';
        setMsg(u.msg, 'error');
        btnInstall.disabled = false;
        btnSkip.style.display = 'inline-block';
      }
    }, 300);
  }

  async function doInstall() {
    btnInstall.disabled = true;
    btnSkip.style.display = 'none';
    statusIcon.textContent = '⏳';
    const count = missingItems.length;
    msgBox.innerHTML = '<div class="spinner" style="display:inline-block"></div> Đang cài đặt ' + count + ' thành phần, vui lòng chờ...';
    msgBox.className = 'msg installing';
    startPollInstall();
    await pywebview.api.do_install(missingItems);
  }

  function doSkip() {
    if (canWork) {
      startUpdateCheck();
    } else {
      pywebview.api.proceed();
    }
  }
</script>
</body>
</html>
"""

# ── Main App HTML ──────────────────────────────────────────────
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
  <button class="btn-folder" onclick="openFolder()">📂 Mở folder</button>
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

  async function openFolder() {
    await pywebview.api.open_folder();
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

    def open_folder(self) -> None:
        path = self._save_dir
        os.makedirs(path, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        else:
            subprocess.Popen(["xdg-open", path])

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


APP_TITLE = "Video Downloader"


class SetupApi:
    """API cho màn hình kiểm tra dependencies."""

    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._install_updates: list[dict[str, str]] = []
        self._lock = threading.Lock()
        self._update_result: dict | None = None
        self._update_checking: bool = False

    def run_check(self) -> dict[str, object]:
        result = check_deps()
        deps = []
        for pkg in result["packages"]:
            dep: dict[str, str] = {"name": pkg["display"]}
            if pkg["status"] == "ok":
                note = pkg.get("note", "")
                ver = pkg.get("version")
                if ver:
                    note = f"v{ver}" if not note else f"{note}, v{ver}"
                dep["status"] = "ok"
                dep["note"] = note or ""
            elif pkg["status"] == "bundled":
                dep["status"] = "bundled"
                dep["note"] = "chat luong co the bi gioi han"
            elif pkg["status"] == "optional":
                dep["status"] = "bundled"
                dep["note"] = "tuy chon"
            else:
                dep["status"] = "missing"
                dep["note"] = ""
            deps.append(dep)

        all_ok = result["optimal"] and result["ready"]
        can_work = result["ready"]
        missing = result["missing_required"]

        return {
            "deps": deps,
            "all_ok": all_ok,
            "can_work": can_work,
            "missing": missing,
            "has_system_ffmpeg": result["has_system_ffmpeg"],
            "has_bundled_ffmpeg": result["has_bundled_ffmpeg"],
        }

    def do_install(self, items: list[str] | None = None) -> None:
        def _worker() -> None:
            to_install = items or []
            total = len(to_install)
            done = 0
            errors = []

            for item in to_install:
                done += 1
                with self._lock:
                    self._install_updates.append(
                        {"status": "installing",
                         "msg": f"[{done}/{total}] Dang cai {item}..."})

                if item == "ffmpeg":
                    ok, msg = install_ffmpeg()
                    if not ok:
                        errors.append(f"ffmpeg: {msg}")
                else:
                    ok, msg = install_missing_packages([item])
                    if not ok:
                        errors.append(f"{item}: {msg}")

            with self._lock:
                if errors:
                    self._install_updates.append(
                        {"status": "error",
                         "msg": "Loi: " + "; ".join(errors)})
                else:
                    self._install_updates.append(
                        {"status": "done",
                         "msg": f"Da cai dat thanh cong {total} thanh phan!"})
        threading.Thread(target=_worker, daemon=True).start()

    def poll_install(self) -> dict[str, str] | None:
        with self._lock:
            if self._install_updates:
                return self._install_updates.pop(0)
        return None

    def start_update_check(self) -> None:
        """Bắt đầu kiểm tra bản cập nhật mới trên GitHub (background)."""
        self._update_result = None
        self._update_checking = True

        def _worker() -> None:
            from updater import check_update
            try:
                result = check_update(timeout=10)
            except Exception:
                result = {
                    "available": False, "current": "", "latest": "",
                    "download_url": "", "release_url": "", "notes": "",
                }
            self._update_result = result
            self._update_checking = False

        threading.Thread(target=_worker, daemon=True).start()

    def poll_update_check(self) -> dict | None:
        """Trả None nếu đang kiểm tra, dict khi có kết quả."""
        if self._update_checking:
            return None
        return self._update_result

    def do_download_install(self, download_url: str, release_url: str = "") -> None:
        """Tải bản cập nhật về và mở installer."""
        def _worker() -> None:
            import platform as _plat
            import subprocess as _sub

            if not download_url:
                # Không có file trực tiếp — mở trang release trên trình duyệt
                if release_url:
                    system = _plat.system()
                    if system == "Darwin":
                        _sub.Popen(["open", release_url])
                    elif system == "Windows":
                        _sub.Popen(["start", "", release_url], shell=True)
                    else:
                        _sub.Popen(["xdg-open", release_url])
                with self._lock:
                    self._install_updates.append({
                        "status": "error",
                        "msg": "Khong co file tai truc tiep.\nTrang GitHub Releases da duoc mo - vui long tai thu cong.",
                    })
                return

            try:
                from updater import download_update

                def _progress(pct: int) -> None:
                    with self._lock:
                        self._install_updates.append({
                            "status": "installing",
                            "msg": f"Dang tai ban cap nhat... {pct}%",
                        })

                path = download_update(download_url, _progress)
                with self._lock:
                    self._install_updates.append({
                        "status": "ready",
                        "path": path,
                        "msg": "Tai xong! Dang mo cai dat va thoat ung dung...",
                    })
            except Exception as e:
                with self._lock:
                    self._install_updates.append({
                        "status": "error",
                        "msg": f"Loi tai cap nhat: {e}",
                    })

        threading.Thread(target=_worker, daemon=True).start()

    def install_now(self, path: str) -> None:
        """Mở file installer rồi đóng app hiện tại."""
        import platform as _plat
        import subprocess as _sub

        system = _plat.system()
        if system == "Darwin":
            _sub.Popen(["open", path])
        elif system == "Windows":
            _sub.Popen([path])
        else:
            _sub.Popen(["xdg-open", path])

        def _close() -> None:
            import time
            time.sleep(0.8)
            if self._window:
                self._window.destroy()

        threading.Thread(target=_close, daemon=True).start()

    def proceed(self) -> None:
        """Chuyển sang màn hình chính."""
        if not self._window:
            return

        def _do_load() -> None:
            import time
            time.sleep(0.1)  # đợi pywebview trả callback về JS trước
            api = Api()
            self._window.load_html(HTML)
            self._window.resize(800, 650)
            self._window._js_api = api  # type: ignore[attr-defined]
            self._window.expose(
                api.get_save_dir,
                api.choose_folder,
                api.start_download,
                api.stop_download,
                api.poll_updates,
            )

        threading.Thread(target=_do_load, daemon=True).start()


def main() -> None:
    setup_api = SetupApi()
    window = webview.create_window(
        APP_TITLE,
        html=SETUP_HTML,
        js_api=setup_api,
        width=520,
        height=480,
        min_size=(520, 480),
    )
    setup_api._window = window
    webview.start(debug=False)


if __name__ == "__main__":
    main()
