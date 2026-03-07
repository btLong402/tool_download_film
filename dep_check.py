"""Dependency checker — kiểm tra và cài đặt các thư viện cần thiết khi mở app."""

import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys

# Danh sách Python packages cần kiểm tra: (import_name, display_name)
REQUIRED_PACKAGES = [
    ("yt_dlp", "yt-dlp"),
    ("requests", "requests"),
    ("m3u8", "m3u8"),
    ("tqdm", "tqdm"),
    ("urllib3", "urllib3"),
    ("webview", "pywebview"),
]

OPTIONAL_PACKAGES = [
    ("imageio_ffmpeg", "imageio-ffmpeg"),
]


def _get_package_version(import_name: str) -> str | None:
    """Lấy version của package. Trả về None nếu không tìm thấy."""
    # Mapping import name → distribution name
    dist_map = {
        "yt_dlp": "yt-dlp",
        "webview": "pywebview",
        "imageio_ffmpeg": "imageio-ffmpeg",
    }
    dist_name = dist_map.get(import_name, import_name)
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        pass
    # Fallback: try importing
    try:
        mod = __import__(import_name)
        for attr in ("__version__", "version", "VERSION"):
            v = getattr(mod, attr, None)
            if v:
                if isinstance(v, str):
                    return v
                # yt_dlp.version module
                if hasattr(v, "__version__"):
                    return v.__version__
    except ImportError:
        pass
    return None


def _check_package(import_name: str) -> tuple[bool, str | None]:
    """Kiểm tra package có import được không. Trả về (available, version)."""
    try:
        __import__(import_name)
        version = _get_package_version(import_name)
        return True, version
    except ImportError:
        return False, None


def has_system_ffmpeg() -> bool:
    """Kiểm tra ffmpeg có trong system PATH."""
    return shutil.which("ffmpeg") is not None


def _get_ffmpeg_version() -> str | None:
    """Lấy version ffmpeg từ system."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        first_line = result.stdout.split("\\n")[0] if result.stdout else ""
        # "ffmpeg version 7.1 Copyright ..."
        parts = first_line.split()
        if len(parts) >= 3:
            return parts[2]
    except Exception:
        pass
    return None


def has_bundled_ffmpeg() -> bool:
    """Kiểm tra ffmpeg bundled trong app (imageio-ffmpeg hoặc PyInstaller)."""
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return True
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        search_dirs = []
        if hasattr(sys, "_MEIPASS"):
            search_dirs.append(sys._MEIPASS)
        search_dirs.append(os.path.dirname(sys.executable))
        for base in search_dirs:
            for root, _dirs, files in os.walk(base):
                for f in files:
                    if f.startswith("ffmpeg") and not f.endswith(".py"):
                        candidate = os.path.join(root, f)
                        if os.access(candidate, os.X_OK):
                            return True
    return False


def check_deps() -> dict[str, object]:
    """Kiểm tra tất cả dependencies.

    Returns dict:
        ready: bool — True nếu đủ deps để chạy
        optimal: bool — True nếu dùng được chất lượng cao nhất
        has_system_ffmpeg: bool
        has_bundled_ffmpeg: bool
        packages: list[dict] — chi tiết từng package
            name, display, available, version, required, status
        missing_required: list[str] — packages bắt buộc nhưng thiếu
    """
    sys_ff = has_system_ffmpeg()
    bun_ff = has_bundled_ffmpeg()
    any_ff = sys_ff or bun_ff

    packages = []

    # ffmpeg (binary)
    ff_version = _get_ffmpeg_version() if sys_ff else None
    if sys_ff:
        packages.append({
            "name": "ffmpeg", "display": "ffmpeg",
            "available": True, "version": ff_version,
            "required": True, "status": "ok", "note": "system",
        })
    elif bun_ff:
        packages.append({
            "name": "ffmpeg", "display": "ffmpeg",
            "available": True, "version": None,
            "required": True, "status": "bundled", "note": "bundled",
        })
    else:
        packages.append({
            "name": "ffmpeg", "display": "ffmpeg",
            "available": False, "version": None,
            "required": True, "status": "missing", "note": "",
        })

    # Python packages (required)
    for import_name, display_name in REQUIRED_PACKAGES:
        avail, version = _check_package(import_name)
        packages.append({
            "name": import_name, "display": display_name,
            "available": avail, "version": version,
            "required": True,
            "status": "ok" if avail else "missing",
            "note": "",
        })

    # Python packages (optional)
    for import_name, display_name in OPTIONAL_PACKAGES:
        avail, version = _check_package(import_name)
        packages.append({
            "name": import_name, "display": display_name,
            "available": avail, "version": version,
            "required": False,
            "status": "ok" if avail else "optional",
            "note": "optional" if not avail else "",
        })

    missing_required = [p["display"] for p in packages
                        if p["required"] and not p["available"]]

    ready = all(p["available"] for p in packages if p["required"])

    return {
        "ready": ready,
        "optimal": sys_ff,
        "has_system_ffmpeg": sys_ff,
        "has_bundled_ffmpeg": bun_ff,
        "packages": packages,
        "missing_required": missing_required,
    }


def install_ffmpeg() -> tuple[bool, str]:
    """Cài đặt ffmpeg qua package manager.

    Returns (success, message).
    """
    system = platform.system()

    if system == "Darwin":
        # macOS — Homebrew
        if not shutil.which("brew"):
            # Cài Homebrew trước
            try:
                subprocess.run(
                    ["/bin/bash", "-c",
                     'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'],
                    check=True, timeout=300,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return False, "Khong the cai Homebrew. Hay cai thu cong: https://brew.sh"

        try:
            subprocess.run(
                ["brew", "install", "ffmpeg"],
                check=True, timeout=600,
                capture_output=True,
            )
            return True, "Da cai ffmpeg thanh cong qua Homebrew."
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            return False, f"Loi khi cai ffmpeg: {e}"

    elif system == "Windows":
        # Windows — winget hoặc choco
        if shutil.which("winget"):
            try:
                subprocess.run(
                    ["winget", "install", "Gyan.FFmpeg",
                     "--accept-source-agreements", "--accept-package-agreements"],
                    check=True, timeout=600,
                    capture_output=True,
                )
                return True, "Da cai ffmpeg thanh cong qua winget."
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

        if shutil.which("choco"):
            try:
                subprocess.run(
                    ["choco", "install", "ffmpeg", "-y"],
                    check=True, timeout=600,
                    capture_output=True,
                )
                return True, "Da cai ffmpeg thanh cong qua Chocolatey."
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass

        return False, "Khong the tu dong cai ffmpeg. Tai tai: https://ffmpeg.org/download.html"

    else:
        # Linux
        for cmd in [["sudo", "apt", "install", "-y", "ffmpeg"],
                    ["sudo", "dnf", "install", "-y", "ffmpeg"]]:
            if shutil.which(cmd[1]):
                try:
                    subprocess.run(cmd, check=True, timeout=300, capture_output=True)
                    return True, "Da cai ffmpeg thanh cong."
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    continue
        return False, "Hay cai ffmpeg thu cong: sudo apt install ffmpeg"


def install_missing_packages(packages: list[str]) -> tuple[bool, str]:
    """Cai dat Python packages thieu bang pip.

    Returns (success, message).
    """
    if not packages:
        return True, "Khong co gi can cai."

    python = sys.executable
    try:
        subprocess.run(
            [python, "-m", "pip", "install", "--upgrade"] + packages,
            check=True, timeout=300,
            capture_output=True,
        )
        return True, f"Da cai thanh cong: {', '.join(packages)}"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return False, f"Loi khi cai {', '.join(packages)}: {e}"
