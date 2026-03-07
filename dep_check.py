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


# Các đường dẫn phổ biến chứa ffmpeg/brew — macOS/Linux + Windows
def _get_extra_paths() -> list[str]:
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


def _find_executable(name: str) -> str | None:
    """Tìm executable: shutil.which trước, sau đó quét đường dẫn phổ biến."""
    found = shutil.which(name)
    if found:
        return found
    # Trên Windows cần thêm .exe
    suffixes = ["", ".exe"] if sys.platform == "win32" else [""]
    for d in _get_extra_paths():
        for suffix in suffixes:
            candidate = os.path.join(d, name + suffix)
            if os.path.isfile(candidate):
                if sys.platform != "win32" and not os.access(candidate, os.X_OK):
                    continue
                return candidate
    return None


def has_system_ffmpeg() -> bool:
    """Kiểm tra ffmpeg có trong system PATH hoặc đường dẫn phổ biến."""
    return _find_executable("ffmpeg") is not None


def _get_ffmpeg_version() -> str | None:
    """Lấy version ffmpeg từ system."""
    ffmpeg_bin = _find_executable("ffmpeg")
    if not ffmpeg_bin:
        return None
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=5
        )
        first_line = result.stdout.split("\n")[0] if result.stdout else ""
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


def _clean_env() -> dict[str, str]:
    """Tạo env sạch cho subprocess — loại bỏ biến PyInstaller/venv gây nhiễu,
    và đảm bảo PATH chứa các đường dẫn phổ biến."""
    env = dict(os.environ)
    # Loại bỏ biến Python của PyInstaller/venv có thể gây lỗi cho brew/choco
    for key in list(env.keys()):
        if key.startswith("PYTHON") or key in ("VIRTUAL_ENV", "CONDA_PREFIX"):
            del env[key]
    # Đảm bảo PATH chứa các đường dẫn phổ biến
    path_dirs = env.get("PATH", "").split(os.pathsep)
    for extra in _get_extra_paths():
        if extra not in path_dirs:
            path_dirs.append(extra)
    env["PATH"] = os.pathsep.join(path_dirs)
    return env


def install_ffmpeg() -> tuple[bool, str]:
    """Cài đặt ffmpeg qua package manager.

    Returns (success, message).
    """
    system = platform.system()
    env = _clean_env()

    if system == "Darwin":
        # macOS — Homebrew
        brew_bin = _find_executable("brew")
        if not brew_bin:
            # Thử cài Homebrew
            try:
                env["NONINTERACTIVE"] = "1"
                subprocess.run(
                    ["/bin/bash", "-c",
                     'curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh | bash'],
                    check=True, timeout=600,
                    capture_output=True, text=True, env=env,
                )
                brew_bin = _find_executable("brew")
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or "")[:300]
                return False, f"Khong the cai Homebrew: {stderr}\nCai thu cong: https://brew.sh"
            except subprocess.TimeoutExpired:
                return False, "Het thoi gian cai Homebrew. Cai thu cong: https://brew.sh"

        if not brew_bin:
            return False, "Khong tim thay Homebrew.\nCai thu cong: https://brew.sh\nSau do chay: brew install ffmpeg"

        try:
            result = subprocess.run(
                [brew_bin, "install", "ffmpeg"],
                check=True, timeout=900,
                capture_output=True, text=True, env=env,
            )
            return True, "Da cai ffmpeg thanh cong qua Homebrew."
        except subprocess.CalledProcessError as e:
            output = (e.stdout or "") + (e.stderr or "")
            if "already installed" in output.lower():
                return True, "ffmpeg da duoc cai san."
            return False, f"Loi brew install ffmpeg:\n{(e.stderr or output)[:300]}"
        except subprocess.TimeoutExpired:
            return False, "Het thoi gian cho. Chay thu cong: brew install ffmpeg"

    elif system == "Windows":
        # Windows — winget hoặc choco
        winget_bin = _find_executable("winget")
        if winget_bin:
            try:
                subprocess.run(
                    [winget_bin, "install", "Gyan.FFmpeg",
                     "--accept-source-agreements", "--accept-package-agreements",
                     "--disable-interactivity"],
                    check=True, timeout=900,
                    capture_output=True, text=True, env=env,
                )
                return True, "Da cai ffmpeg thanh cong qua winget."
            except subprocess.CalledProcessError as e:
                output = ((e.stdout or "") + (e.stderr or "")).lower()
                if "already installed" in output:
                    return True, "ffmpeg da duoc cai san."
                # winget có thể cần cửa sổ admin — tiếp tục thử choco
            except subprocess.TimeoutExpired:
                pass

        choco_bin = _find_executable("choco")
        if choco_bin:
            try:
                subprocess.run(
                    [choco_bin, "install", "ffmpeg", "-y", "--no-progress"],
                    check=True, timeout=900,
                    capture_output=True, text=True, env=env,
                )
                return True, "Da cai ffmpeg thanh cong qua Chocolatey."
            except subprocess.CalledProcessError as e:
                output = ((e.stdout or "") + (e.stderr or "")).lower()
                if "already installed" in output:
                    return True, "ffmpeg da duoc cai san."
                if "access" in output or "admin" in output or "elevated" in output:
                    return False, ("Can quyen Admin. Mo cmd voi 'Run as Administrator'"
                                   " roi chay:\n  choco install ffmpeg -y")
            except subprocess.TimeoutExpired:
                pass

        # Không có winget/choco
        msg_lines = ["Khong the tu dong cai ffmpeg."]
        if winget_bin:
            msg_lines.append("Cach 1: Mo cmd (Admin) > winget install Gyan.FFmpeg")
        if choco_bin:
            msg_lines.append("Cach 2: Mo cmd (Admin) > choco install ffmpeg -y")
        msg_lines.append("Thu cong: Tai https://www.gyan.dev/ffmpeg/builds/")
        msg_lines.append("  giai nen vao C:\\ffmpeg va them C:\\ffmpeg\\bin vao PATH")
        return False, "\n".join(msg_lines)

    else:
        # Linux
        for cmd in [["sudo", "apt", "install", "-y", "ffmpeg"],
                    ["sudo", "dnf", "install", "-y", "ffmpeg"]]:
            if shutil.which(cmd[1]):
                try:
                    subprocess.run(cmd, check=True, timeout=300,
                                   capture_output=True, text=True, env=env)
                    return True, "Da cai ffmpeg thanh cong."
                except subprocess.CalledProcessError:
                    continue
                except subprocess.TimeoutExpired:
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
        result = subprocess.run(
            [python, "-m", "pip", "install", "--upgrade"] + packages,
            check=True, timeout=300,
            capture_output=True, text=True,
        )
        return True, f"Da cai thanh cong: {', '.join(packages)}"
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "")[:300]
        return False, f"Loi khi cai {', '.join(packages)}:\n{stderr}"
    except subprocess.TimeoutExpired:
        return False, f"Het thoi gian cai {', '.join(packages)}. Thu chay thu cong: pip install {' '.join(packages)}"
