"""Build script — đóng gói Video Downloader thành app có thể cài đặt.

Chạy:
    python build.py                (macOS → .dmg trong dist/)
    python build.py                (Windows → Setup .exe trong dist/)

Yêu cầu:
    pip install -r requirements.txt pyinstaller imageio-ffmpeg Pillow
"""

import os
import platform
import shutil
import subprocess
import sys

APP_NAME = "Video Downloader"
APP_VERSION = "1.0.0"
BUNDLE_ID = "com.videodownloader.app"


def _generate_icon() -> str | None:
    """生成 app icon nếu chưa có. Trả về path .icns (macOS) hoặc .ico (Windows)."""
    system = platform.system()

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("⚠ Không có Pillow, bỏ qua tạo icon. (pip install Pillow)")
        return None

    # Tạo icon 1024x1024
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2

    # Vòng tròn nền
    r = 480
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 30, 46, 255))
    r2 = 440
    draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(49, 50, 68, 255))

    # Tam giác play
    tri_x, tri_y, tri_size = cx - 40, cy, 260
    draw.polygon([
        (tri_x - tri_size // 3, tri_y - tri_size // 2),
        (tri_x - tri_size // 3, tri_y + tri_size // 2),
        (tri_x + tri_size * 2 // 3, tri_y),
    ], fill=(137, 180, 250, 255))

    # Mũi tên download
    acx, acy, aw, ah, at = cx + 200, cy + 200, 60, 80, 50
    draw.rectangle([acx - aw // 3, acy - ah, acx + aw // 3, acy], fill=(166, 227, 161, 255))
    draw.polygon([(acx - aw, acy), (acx + aw, acy), (acx, acy + at)], fill=(166, 227, 161, 255))
    draw.rectangle([acx - aw, acy + at + 10, acx + aw, acy + at + 18], fill=(166, 227, 161, 255))

    img.save("icon.png")

    if system == "Darwin":
        # Tạo .icns từ iconset
        iconset = "icon.iconset"
        os.makedirs(iconset, exist_ok=True)
        for s in [16, 32, 64, 128, 256, 512]:
            img.resize((s, s), Image.LANCZOS).save(os.path.join(iconset, f"icon_{s}x{s}.png"))
            s2 = s * 2
            if s2 <= 1024:
                img.resize((s2, s2), Image.LANCZOS).save(os.path.join(iconset, f"icon_{s}x{s}@2x.png"))
        img.save(os.path.join(iconset, "icon_512x512@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", "icon.icns"], check=True)
        shutil.rmtree(iconset, ignore_errors=True)
        print("✅ Tạo icon.icns")
        return "icon.icns"
    else:
        # Windows/Linux: tạo .ico
        ico_sizes = [img.resize((s, s), Image.LANCZOS) for s in [16, 32, 48, 64, 128, 256]]
        ico_sizes[0].save("icon.ico", format="ICO", sizes=[(s, s) for s in [16, 32, 48, 64, 128, 256]],
                          append_images=ico_sizes[1:])
        print("✅ Tạo icon.ico")
        return "icon.ico"


def _create_dmg(app_path: str) -> str:
    """Tạo .dmg installer cho macOS."""
    dmg_name = f"{APP_NAME}-{APP_VERSION}-macOS.dmg"
    dmg_path = os.path.join("dist", dmg_name)

    # Xoá dmg cũ nếu có
    if os.path.exists(dmg_path):
        os.remove(dmg_path)

    print(f"\nĐang tạo {dmg_name}...")

    # Tạo temporary DMG staging folder
    staging = os.path.join("dist", "dmg_staging")
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    # Copy .app vào staging
    dest_app = os.path.join(staging, f"{APP_NAME}.app")
    shutil.copytree(app_path, dest_app, symlinks=True)

    # Tạo symlink Applications
    os.symlink("/Applications", os.path.join(staging, "Applications"))

    # Tạo DMG bằng hdiutil
    subprocess.run([
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", staging,
        "-ov",
        "-format", "UDZO",  # compressed
        dmg_path,
    ], check=True)

    shutil.rmtree(staging, ignore_errors=True)
    print(f"✅ DMG: {dmg_path}")
    return dmg_path


def _create_windows_installer_script() -> str:
    """Tạo Inno Setup script (.iss) cho Windows installer."""
    iss_content = f"""; Inno Setup Script for {APP_NAME}
[Setup]
AppName={APP_NAME}
AppVersion={APP_VERSION}
AppPublisher=Video Downloader
DefaultDirName={{autopf}}\\{APP_NAME}
DefaultGroupName={APP_NAME}
OutputDir=dist
OutputBaseFilename={APP_NAME}-{APP_VERSION}-Windows-Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={{app}}\\{APP_NAME}.exe
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Files]
Source: "dist\\{APP_NAME}.exe"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{group}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"
Name: "{{commondesktop}}\\{APP_NAME}"; Filename: "{{app}}\\{APP_NAME}.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{{app}}\\{APP_NAME}.exe"; Description: "Launch {APP_NAME}"; Flags: nowait postinstall skipifsilent
"""
    iss_path = "installer.iss"
    with open(iss_path, "w") as f:
        f.write(iss_content)
    print(f"✅ Tạo {iss_path} (dùng Inno Setup để build installer)")
    return iss_path


def main() -> None:
    system = platform.system()
    app_name = APP_NAME

    print(f"Building {APP_NAME} v{APP_VERSION} for {system}...")
    print()

    # ── Tạo icon ───────────────────────────────────────────────
    icon_path = _generate_icon()

    # ── Tìm đường dẫn ffmpeg binary từ imageio-ffmpeg ──────────
    try:
        import imageio_ffmpeg
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_bin)
    except ImportError:
        print("Lỗi: Chưa cài imageio-ffmpeg. Chạy: pip install imageio-ffmpeg")
        sys.exit(1)

    # ── Xây dựng lệnh PyInstaller ──────────────────────────────
    cmd: list[str] = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", app_name,
        # Collect yt-dlp đầy đủ (nhiều extractors)
        "--collect-all", "yt_dlp",
        # Collect imageio-ffmpeg (binary ffmpeg)
        "--collect-all", "imageio_ffmpeg",
        # pywebview hidden imports
        "--hidden-import", "webview",
        "--hidden-import", "bottle",
        "--hidden-import", "proxy_tools",
        # Libs
        "--hidden-import", "m3u8",
        "--hidden-import", "requests",
        "--hidden-import", "tqdm",
        "--hidden-import", "urllib3",
        "--hidden-import", "charset_normalizer",
        "--hidden-import", "certifi",
    ]

    if icon_path:
        cmd += ["--icon", icon_path]

    if system == "Darwin":
        cmd += [
            "--windowed",                  # .app bundle
            "--onedir",                    # thư mục (ổn định hơn onefile)
            # macOS pywebview cần pyobjc
            "--hidden-import", "objc",
            "--hidden-import", "Foundation",
            "--hidden-import", "AppKit",
            "--hidden-import", "WebKit",
            "--hidden-import", "PyObjCTools",
            "--collect-all", "pyobjc-core",
            "--collect-all", "pyobjc-framework-Cocoa",
            "--collect-all", "pyobjc-framework-WebKit",
            "--collect-all", "pyobjc-framework-Quartz",
        ]
    elif system == "Windows":
        cmd += [
            "--windowed",                  # không hiện console
            "--onefile",                   # 1 file .exe duy nhất
            # Windows pywebview dùng EdgeChromium (mặc định)
            "--hidden-import", "clr",
            "--hidden-import", "pythonnet",
        ]
    else:
        # Linux
        cmd += [
            "--onefile",
            "--hidden-import", "gi",
        ]

    # Entry point
    cmd.append("app.py")

    print("Lệnh build:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nBuild thất bại (exit code {result.returncode}).")
        sys.exit(1)

    # ── Kết quả ────────────────────────────────────────────────
    print()
    print("=" * 50)
    print("✅ Build thành công!")

    if system == "Darwin":
        app_path = f"dist/{app_name}.app"
        print(f"   App: {app_path}")
        # Tạo DMG installer
        dmg_path = _create_dmg(app_path)
        print()
        print("=" * 50)
        print(f"📦 Release file: {dmg_path}")
        print(f"   Người dùng chỉ cần mở .dmg và kéo app vào Applications.")
    elif system == "Windows":
        print(f"   App: dist\\{app_name}.exe")
        _create_windows_installer_script()
        # Nếu có Inno Setup, tự động build installer
        iscc = shutil.which("iscc") or shutil.which("ISCC")
        if iscc:
            print("\nĐang tạo installer...")
            subprocess.run([iscc, "installer.iss"], check=True)
            print(f"📦 Release file: dist/{app_name}-{APP_VERSION}-Windows-Setup.exe")
        else:
            print()
            print("Để tạo installer:")
            print("  1. Cài Inno Setup: https://jrsoftware.org/isintl.php")
            print("  2. Chạy: iscc installer.iss")
            print(f"  → Kết quả: dist/{app_name}-{APP_VERSION}-Windows-Setup.exe")
    else:
        print(f"   App: dist/{app_name}")

    print("=" * 50)


if __name__ == "__main__":
    main()
