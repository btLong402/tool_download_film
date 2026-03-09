<div align="center">

# 🎬 Video Downloader

**A powerful, cross-platform video downloader with a beautiful dark-themed GUI.**\
Supports **1800+ websites** including YouTube, Facebook, TikTok, Instagram, Vimeo, and more.

[![Version](https://img.shields.io/badge/version-1.1.4-blue.svg)](https://github.com/btLong402/tool_download_film/releases)
[![Python](https://img.shields.io/badge/python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)]()

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🌐 **1800+ Sites** | YouTube, Facebook, TikTok, Instagram, Twitter/X, Vimeo, Dailymotion, rophim, and many more |
| 📋 **Batch Download** | Paste multiple links (one per line) — downloads sequentially and automatically |
| 📁 **Custom Save Location** | Choose any folder to save your videos |
| 🎨 **Modern UI** | Dark theme with real-time progress display |
| ⏹️ **Safe Cancel** | Stop downloads safely at any time |
| 🔄 **Auto Update** | Checks for new versions from GitHub Releases |
| 🖥️ **Cross-platform** | Runs on macOS and Windows |

## 📸 Screenshots

<!-- Add screenshots here -->
<!-- ![Main Window](docs/screenshot-main.png) -->

## 📦 Installation

### Download Pre-built Binaries

<details>
<summary><strong>🍎 macOS</strong></summary>

1. Download `Video Downloader-x.x.x-macOS.dmg` from [**Releases**](https://github.com/btLong402/tool_download_film/releases)
2. Open the `.dmg` file
3. Drag **Video Downloader** into your **Applications** folder
4. Launch from Applications

</details>

<details>
<summary><strong>🪟 Windows</strong></summary>

1. Download `Video Downloader-x.x.x-Windows-Setup.exe` from [**Releases**](https://github.com/btLong402/tool_download_film/releases)
2. Run the Setup installer
3. Follow the installation wizard
4. Launch from Start Menu or Desktop shortcut

</details>

## 🛠️ Development

### Prerequisites

- **Python** 3.12 or higher
- **ffmpeg** (auto-installed on first run, or install manually via `brew install ffmpeg` / `choco install ffmpeg`)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/btLong402/tool_download_film.git
cd tool_download_film

# Create virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
pip install pyinstaller imageio-ffmpeg Pillow
```

### Running Locally

```bash
# Launch GUI application
python app.py

# Run CLI downloader
python rophim_downloader.py
```

### Building for Distribution

```bash
python build.py
```

Output artifacts:
| Platform | Output |
|----------|--------|
| macOS    | `dist/Video Downloader-x.x.x-macOS.dmg` |
| Windows  | `dist/Video Downloader-x.x.x-Windows-Setup.exe` |

### Creating a Release

Push a version tag to trigger GitHub Actions CI/CD:

```bash
git tag v1.1.4
git push origin v1.1.4
```

## 🏗️ Project Structure

```
├── app.py                  # Main GUI application (pywebview)
├── rophim_downloader.py    # Core download engine (yt-dlp + m3u8)
├── dep_check.py            # Dependency checker & auto-installer
├── updater.py              # Auto-update from GitHub Releases
├── build.py                # Build script (PyInstaller → DMG / EXE)
├── version.py              # Single source of truth for versioning
├── requirements.txt        # Python dependencies
└── Video Downloader.spec   # PyInstaller spec file
```

## 🧰 Tech Stack

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — Video extraction & download engine
- **[pywebview](https://pywebview.flowrl.com/)** — Lightweight native GUI wrapper
- **[m3u8](https://github.com/globocom/m3u8)** — HLS stream parsing
- **[PyInstaller](https://pyinstaller.org/)** — Packaging into standalone executables
- **[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)** — Bundled ffmpeg binary

## 🤝 Contributing

Contributions are welcome! Feel free to:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Made with ❤️ by [btLong402](https://github.com/btLong402)

</div>
