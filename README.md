# 🎬 Video Downloader

Ứng dụng tải video từ **mọi trang web** — hỗ trợ 1800+ trang bao gồm YouTube, Facebook, TikTok, Instagram, Vimeo, rophim, ...

## ✨ Tính năng

- **Hỗ trợ 1800+ trang web** — YouTube, Facebook, TikTok, Instagram, Twitter/X, Vimeo, Dailymotion, rophim, ...
- **Paste nhiều link** — mỗi dòng 1 link, tải lần lượt tự động
- **Chọn folder lưu** — tự do chọn nơi lưu video
- **Giao diện đẹp** — dark theme, hiển thị tiến trình realtime
- **Nút Dừng** — dừng an toàn bất cứ lúc nào
- **Cross-platform** — chạy trên macOS và Windows

## 📦 Cài đặt

### macOS
1. Tải file `Video Downloader-x.x.x-macOS.dmg` từ [Releases](../../releases)
2. Mở file `.dmg`
3. Kéo **Video Downloader** vào thư mục **Applications**
4. Mở app từ Applications

### Windows
1. Tải file `Video Downloader-x.x.x-Windows-Setup.exe` từ [Releases](../../releases)
2. Chạy file Setup
3. Làm theo hướng dẫn cài đặt
4. Mở app từ Start Menu hoặc Desktop

## 🛠 Phát triển

### Yêu cầu
- Python 3.12+

### Cài đặt môi trường
```bash
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
pip install pyinstaller imageio-ffmpeg Pillow
```

### Chạy trực tiếp
```bash
# GUI
python app.py

# CLI
python rophim_downloader.py
```

### Build release
```bash
python build.py
```

Kết quả:
- **macOS**: `dist/Video Downloader-x.x.x-macOS.dmg`
- **Windows**: `dist/Video Downloader-x.x.x-Windows-Setup.exe`

### Tạo release tự động
Push tag version để GitHub Actions tự động build và tạo release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 📄 License

MIT
