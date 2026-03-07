"""Auto-updater — kiểm tra bản mới từ GitHub Releases và tải về."""

import json
import os
import platform
import tempfile
import urllib.error
import urllib.request


def _parse_version(v: str) -> tuple[int, ...]:
    """'v1.2.3' hoặc '1.2.3' → (1, 2, 3). Trả (0,) nếu parse lỗi."""
    v = v.lstrip("v").strip()
    try:
        parts = [int(x) for x in v.split(".") if x.isdigit()]
        return tuple(parts) if parts else (0,)
    except ValueError:
        return (0,)


def check_update(timeout: int = 10) -> dict:
    """Kiểm tra GitHub Releases API xem có bản mới hơn version hiện tại không.

    Returns dict:
        available: bool        — True nếu có bản mới
        current: str           — version đang chạy
        latest: str            — version mới nhất trên GitHub
        download_url: str      — URL installer (macOS .dmg / Windows .exe)
        release_url: str       — URL trang release trên GitHub
        notes: str             — Release notes (rút gọn)
    """
    from version import APP_VERSION, GITHUB_REPO

    current = APP_VERSION
    empty: dict = {
        "available": False, "current": current, "latest": current,
        "download_url": "", "release_url": "", "notes": "",
    }

    if not GITHUB_REPO:
        return empty

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": f"VideoDownloader/{current}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: dict = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "").lstrip("v").strip()
        if not latest_tag:
            return empty

        release_url: str = data.get("html_url", "")
        raw_notes: str = data.get("body", "") or ""
        notes = raw_notes[:400] + ("..." if len(raw_notes) > 400 else "")

        available = _parse_version(latest_tag) > _parse_version(current)
        download_url = _find_asset(data.get("assets", []))

        return {
            "available": available,
            "current": current,
            "latest": latest_tag,
            "download_url": download_url,
            "release_url": release_url,
            "notes": notes,
        }
    except Exception:
        return empty


def _find_asset(assets: list) -> str:
    """Tìm URL installer phù hợp với OS hiện tại (.dmg cho macOS, .exe cho Windows)."""
    system = platform.system()
    for asset in assets:
        name: str = asset.get("name", "").lower()
        url: str = asset.get("browser_download_url", "")
        if system == "Darwin" and name.endswith(".dmg"):
            return url
        if system == "Windows" and name.endswith(".exe"):
            return url
    return ""


def download_update(url: str, progress_cb=None) -> str:
    """Tải file installer về thư mục temp. Trả về đường dẫn file đã tải.

    progress_cb(pct: int) sẽ được gọi với % hoàn thành (0-100).
    """
    filename = url.split("/")[-1].split("?")[0] or "VideoDownloader_update"
    dest = os.path.join(tempfile.gettempdir(), filename)

    try:
        # Ưu tiên requests: hỗ trợ stream, redirect, progress tốt hơn
        import requests as _req

        with _req.get(url, stream=True, timeout=120, verify=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and progress_cb:
                            progress_cb(min(100, downloaded * 100 // total))

    except ImportError:
        # Fallback: urllib stdlib nếu requests chưa cài
        def _hook(block: int, bsize: int, total: int) -> None:
            if total > 0 and progress_cb:
                progress_cb(min(100, block * bsize * 100 // total))

        urllib.request.urlretrieve(url, dest, reporthook=_hook)

    return dest
