import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from concurrent import futures as futures_mod
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import m3u8
import requests
import urllib3
import yt_dlp
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

# Type alias cho callback log
LogFunc = Callable[[str], None]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

TIMEOUT = (5, 30)  # (connect, read) seconds
XOR_KEY = "mySecretKey2024"
MAX_WORKERS = 16  # Số luồng tải song song

ROPHIM_PATTERN = re.compile(
    r"rophim",
    re.IGNORECASE,
)


def _build_session():
    """Tạo requests.Session với retry adapter và connection pooling."""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=MAX_WORKERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _validate_url(url: str) -> str:
    """Kiểm tra URL hợp lệ (http/https)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"URL không hợp lệ: {url}")
    return url


def _get_extra_paths() -> list[str]:
    """Đường dẫn phổ biến chứa ffmpeg — macOS/Linux + Windows."""
    paths = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        "/usr/bin",
        "/snap/bin",
        os.path.expanduser("~/bin"),
    ]
    if sys.platform == "win32":
        paths.extend([
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                         "chocolatey", "bin"),
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                         "ffmpeg", "bin"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Microsoft", "WinGet", "Links"),
            os.path.join(os.environ.get("USERPROFILE", ""),
                         "scoop", "shims"),
            r"C:\ffmpeg\bin",
        ])
    return [p for p in paths if p]


def _get_ffmpeg_path() -> str:
    """Tìm ffmpeg: system PATH → common paths → imageio-ffmpeg → bundled (PyInstaller) → raise."""
    # 1. System PATH
    system = shutil.which("ffmpeg")
    if system:
        return system
    # 1b. Common paths (bundled app may have limited PATH)
    suffixes = ["", ".exe"] if sys.platform == "win32" else [""]
    for d in _get_extra_paths():
        for suffix in suffixes:
            candidate = os.path.join(d, "ffmpeg" + suffix)
            if os.path.isfile(candidate):
                if sys.platform != "win32" and not os.access(candidate, os.X_OK):
                    continue
                return candidate
    # 2. imageio-ffmpeg (hoạt động cả dev lẫn frozen)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except (ImportError, Exception):
        pass
    # 3. PyInstaller bundled — tìm trong toàn bộ thư mục app
    if getattr(sys, "frozen", False):
        # onedir: thư mục chứa executable; onefile: sys._MEIPASS
        search_dirs = []
        if hasattr(sys, "_MEIPASS"):
            search_dirs.append(sys._MEIPASS)  # type: ignore[attr-defined]
        search_dirs.append(os.path.dirname(sys.executable))
        for base in search_dirs:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if f.startswith("ffmpeg") and not f.endswith(".py"):
                        candidate = os.path.join(root, f)
                        if os.access(candidate, os.X_OK):
                            return candidate
    raise FileNotFoundError(
        "Không tìm thấy ffmpeg. "
        "macOS: brew install ffmpeg | Windows: choco install ffmpeg"
    )


def _is_rophim_url(url: str) -> bool:
    """Kiểm tra URL có phải rophim không."""
    return bool(ROPHIM_PATTERN.search(url))


def download_with_ytdlp(
    url: str,
    output: str = "video.mp4",
    log: LogFunc = print,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Tải video bằng yt-dlp Python API (hỗ trợ 1000+ trang web)."""
    ffmpeg_path: str | None = None
    try:
        ffmpeg_path = _get_ffmpeg_path()
    except FileNotFoundError:
        pass

    last_pct: list[float] = [0.0]  # dùng list để mutate trong closure

    def progress_hook(d: dict[str, object]) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                pct = downloaded / total * 100
                if progress_callback and pct - last_pct[0] >= 1:
                    last_pct[0] = pct
                    progress_callback(int(downloaded), int(total))
        elif d.get("status") == "finished":
            log("Tải xong, đang xử lý...")

    def _build_opts(fmt: str) -> dict[str, object]:
        opts: dict[str, object] = {
            "format": fmt,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "outtmpl": output,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
        }
        if ffmpeg_path:
            opts["ffmpeg_location"] = os.path.dirname(ffmpeg_path)
        return opts

    log("Đang thử tải bằng yt-dlp...")

    # Lần 1: Thử chất lượng cao nhất (cần ffmpeg để merge video+audio)
    if ffmpeg_path:
        try:
            with yt_dlp.YoutubeDL(_build_opts("bestvideo+bestaudio/best")) as ydl:  # type: ignore[arg-type]
                ydl.download([url])
            log(f"Hoàn thành: {output}")
            return True
        except Exception:
            log("Không thể merge video+audio, thử tải single format...")

    # Lần 2: Fallback single-file format có cả video+audio (không cần ffmpeg merge)
    try:
        with yt_dlp.YoutubeDL(_build_opts("best[vcodec!=none][acodec!=none]/best")) as ydl:  # type: ignore[arg-type]
            ydl.download([url])
        log(f"Hoàn thành: {output}")
        return True
    except Exception as e:
        log(f"yt-dlp không hỗ trợ trang này. ({str(e)[:200]})")
        return False


def get_html(session: requests.Session, url: str, referer: str | None = None) -> str:
    """Tải HTML từ URL."""
    extra_headers: dict[str, str] = {}
    if referer:
        extra_headers["Referer"] = referer
    resp = session.get(url, timeout=TIMEOUT, headers=extra_headers)
    resp.raise_for_status()
    return resp.text


def _hex_xor_decrypt(encrypted: str, key: str) -> str:
    """Giải mã chuỗi hex XOR với key."""
    result: list[str] = []
    for i in range(0, len(encrypted), 2):
        byte_val = int(encrypted[i : i + 2], 16)
        key_char = ord(key[(i // 2) % len(key)])
        result.append(chr(byte_val ^ key_char))
    return "".join(result)


def _find_embed_url(html: str) -> str | None:
    """Tìm URL embed player trong trang chính."""
    match = re.search(r'<iframe[^>]+src="([^"]*embed[^"]*)"', html)
    if match:
        return match.group(1)
    return None


def _extract_encrypted_url(html: str) -> str | None:
    """Trích xuất encrypted_url từ biến episode trong trang embed."""
    match = re.search(r'"encrypted_url"\s*:\s*"([0-9a-fA-F]+)"', html)
    if match:
        return match.group(1)
    return None


def find_m3u8_url(
    session: requests.Session, page_url: str, log: LogFunc = print
) -> str:
    """Tìm URL m3u8 — hỗ trợ cả link trực tiếp và encrypted qua embed."""
    html = get_html(session, page_url)

    # 1. Thử tìm m3u8 trực tiếp trong HTML
    direct = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html)
    if direct:
        return direct[0]

    # 2. Tìm iframe embed URL
    embed_url = _find_embed_url(html)
    if not embed_url:
        raise ValueError(
            "Không tìm thấy link m3u8 hoặc embed player trong trang web."
        )

    # Lấy base domain cho referer
    parsed = urlparse(page_url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"

    log(f"Tìm thấy embed: {embed_url}")
    embed_html = get_html(session, embed_url, referer=referer)

    # 3. Thử tìm m3u8 trực tiếp trong embed
    direct = re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', embed_html)
    if direct:
        return direct[0]

    # 4. Giải mã encrypted_url
    encrypted = _extract_encrypted_url(embed_html)
    if not encrypted:
        raise ValueError(
            "Không tìm thấy encrypted_url trong trang embed."
        )

    m3u8_url = _hex_xor_decrypt(encrypted, XOR_KEY)

    if not m3u8_url.startswith("http"):
        raise ValueError(f"Giải mã thất bại, kết quả không hợp lệ: {m3u8_url}")

    return m3u8_url


def _load_m3u8(url: str) -> m3u8.M3U8:
    """Tải và parse m3u8 playlist, bỏ qua lỗi SSL certificate."""
    session = _build_session()
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return m3u8.loads(resp.text, uri=url)


def choose_best_stream(master_url: str) -> str:
    """Chọn stream có bandwidth cao nhất từ master playlist."""
    playlist = _load_m3u8(master_url)

    if not playlist.playlists:
        return master_url

    best = max(
        playlist.playlists,
        key=lambda p: p.stream_info.bandwidth or 0,
    )

    uri: str = best.uri or ""
    if uri.startswith("http"):
        return uri

    base = master_url.rsplit("/", 1)[0]
    return base + "/" + uri


def _download_segment(
    session: requests.Session, url: str, path: str
) -> str | None:
    """Tải 1 segment về file. Trả về path nếu thành công, None nếu là quảng cáo (404)."""
    resp = session.get(url, timeout=TIMEOUT)
    if resp.status_code == 404:
        return None  # Segment quảng cáo, bỏ qua
    resp.raise_for_status()
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


def download_hls_parallel(
    session: requests.Session,
    m3u8_url: str,
    output: str = "video.mp4",
    log: LogFunc = print,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Tải video HLS song song nhiều segment, merge bằng ffmpeg."""
    playlist = _load_m3u8(m3u8_url)
    base = m3u8_url.rsplit("/", 1)[0]

    # Các pattern quảng cáo cần lọc bỏ
    AD_PATTERNS = ("adjump", "/ad/", "/ads/", "advertisement")

    segments: list[tuple[str, int]] = []
    skipped = 0
    for seg in playlist.segments:
        seg_uri: str = seg.uri or ""
        uri = seg_uri if seg_uri.startswith("http") else base + "/" + seg_uri
        if any(p in uri.lower() for p in AD_PATTERNS):
            skipped += 1
            continue
        segments.append((uri, len(segments)))

    if skipped:
        log(f"Đã bỏ qua {skipped} segments quảng cáo.")

    if not segments:
        raise RuntimeError("Playlist không có segment nào.")

    tmp_dir = tempfile.mkdtemp(prefix="rophim_")
    try:
        log(f"Đang tải {len(segments)} segments ({MAX_WORKERS} luồng)...")

        failed: list[int] = []
        ad_skipped = 0
        done_count = 0
        futures: dict[futures_mod.Future[str | None], int] = {}

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for seg_url, idx in segments:
                path = os.path.join(tmp_dir, f"{idx}.ts")
                fut = executor.submit(_download_segment, session, seg_url, path)
                futures[fut] = idx

            use_tqdm = progress_callback is None
            pbar = tqdm(total=len(segments), unit="seg") if use_tqdm else None
            try:
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        result = fut.result()
                        if result is None:
                            ad_skipped += 1
                    except Exception as e:
                        msg = f"  Lỗi segment {idx}: {e}"
                        if pbar:
                            tqdm.write(msg)
                        else:
                            log(msg)
                        failed.append(idx)
                    done_count += 1
                    if pbar:
                        pbar.update(1)
                    if progress_callback:
                        progress_callback(done_count, len(segments))
            finally:
                if pbar:
                    pbar.close()

        if ad_skipped:
            log(f"Đã bỏ qua {ad_skipped} segments quảng cáo (404).")

        if failed:
            log(f"Cảnh báo: {len(failed)} segments lỗi (không phải 404): {sorted(failed)}")

        # Tạo file list cho ffmpeg concat (chỉ gồm segments tải thành công)
        list_file = os.path.join(tmp_dir, "list.txt")
        included = 0
        with open(list_file, "w") as f:
            for i in range(len(segments)):
                seg_path = os.path.join(tmp_dir, f"{i}.ts")
                if os.path.exists(seg_path):
                    f.write(f"file '{seg_path}'\n")
                    included += 1

        if included == 0:
            raise RuntimeError("Không có segment nào được tải thành công.")

        log(f"Đang ghép {included} segments...")
        ffmpeg_exe = _get_ffmpeg_path()
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-movflags", "+faststart",
                "-y",
                output,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg ghép thất bại (exit code {result.returncode})."
            )

        log(f"Hoàn thành: {output}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _download_via_hls(
    url: str,
    output: str,
    log: LogFunc = print,
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    """Tìm m3u8 trong trang web và tải bằng HLS. Trả về True nếu thành công."""
    _get_ffmpeg_path()  # fail-fast nếu không có ffmpeg
    session = _build_session()

    try:
        m3u8_url = find_m3u8_url(session, url, log=log)
    except (requests.RequestException, ValueError):
        return False

    log(f"Tìm thấy m3u8: {m3u8_url}")

    try:
        best = choose_best_stream(m3u8_url)
    except Exception as e:
        log(f"Lỗi khi phân tích playlist: {e}")
        return False

    log(f"Stream tốt nhất: {best}")

    download_hls_parallel(session, best, output, log=log, progress_callback=progress_callback)
    return True


def download_single_url(
    url: str,
    output: str,
    log: LogFunc = print,
    progress_callback: Callable[[int, int], None] | None = None,
) -> None:
    """Tải 1 URL với routing tự động: rophim → HLS, khác → yt-dlp → HLS fallback."""
    _validate_url(url)

    if _is_rophim_url(url):
        log("Phát hiện link rophim, dùng HLS downloader...")
        if not _download_via_hls(url, output, log=log, progress_callback=progress_callback):
            raise RuntimeError("Không tìm thấy video trên trang rophim.")
    else:
        if not download_with_ytdlp(url, output, log=log, progress_callback=progress_callback):
            log("")
            log("Đang thử tìm stream HLS trong trang web...")
            if not _download_via_hls(url, output, log=log, progress_callback=progress_callback):
                raise RuntimeError(
                    "Không thể tải video từ URL này. "
                    "Trang web có thể không được hỗ trợ hoặc cần đăng nhập."
                )


def main():
    url = input("Link phim (hỗ trợ mọi trang web): ").strip()
    if not url:
        print("Lỗi: Chưa nhập link.")
        sys.exit(1)

    output = input("Tên file (Enter = video.mp4): ").strip() or "video.mp4"
    if not output.endswith(".mp4"):
        output += ".mp4"

    try:
        download_single_url(url, output)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"Lỗi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()