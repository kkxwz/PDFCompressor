# SlimPDF

<p align="center">
  <img src="static/images/logo.png" width="80" alt="SlimPDF Logo">
</p>

<p align="center">
  <b>One-click PDF compression. Local processing. Privacy first.</b>
</p>

<p align="center">
  <a href="#download">Download</a> ·
  <a href="#features">Features</a> ·
  <a href="#story">Story</a> ·
  <a href="#support">Support</a> ·
  <a href="#contributing">Contributing</a>
</p>

<p align="center">
  <a href="README.md">简体中文</a> · <a href="README.en.md">English</a>
</p>

---

## 📸 Preview

<p align="center">
  <img src="docs/images/screenshot.png" width="720" alt="SlimPDF Screenshot">
</p>

> Drag in → Pick quality → Done in 3s → Download

---

## 💝 Story

**Every developer is the "IT department" for their family.**

You know the drill. It's Sunday evening. Your partner sends you an 80MB scanned PDF. "It's too big for WeChat. Can you compress it?"

You open your terminal. `gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 ...` Tweak parameters. Wait. Try again. Third time's the charm.

"Thanks, honey!"

A week later, same file, same ritual.

The third time, it hit me: I've built complex systems, scaled services, optimized databases — but I never actually solved the simplest problem for the person closest to me.

Not because I couldn't. Because I never thought she deserved a tool that just *worked* with one click.

So that weekend, instead of LeetCode or tech blogs, I built this. Drag in. Click. Wait 3 seconds. Done.

She doesn't need me for this anymore.

I'm a little sad. And a lot proud.

**That's why this exists.**

If you've ever been the family IT department, if you've ever wanted your skills to make someone's day a little easier — I hope this helps.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🚀 **3 Compression Levels** | Low (high quality) / Medium (balanced) / High (smallest size) |
| 🔒 **Local Processing** | Files never leave your machine. Zero privacy risk. |
| 📉 **Smart Optimization** | Deduplicate images, subset fonts, convert color spaces |
| 🖥️ **Cross-Platform** | macOS (Universal) / Windows (x64) |
| 🎯 **One-Click** | Drag → Select → Done. No technical knowledge needed. |
| 🌙 **Dark Mode** | Dark / Light / System theme support |

---

## 📥 Download

Go to [Releases](https://github.com/kkxwz/PDFCompressor/releases) for the latest builds.

| Platform | Download | Notes |
|----------|----------|-------|
| macOS | `SlimPDF-macOS.dmg` | Universal Binary (Intel + Apple Silicon) |
| Windows | `SlimPDF-Windows-x64.exe` | 64-bit Windows 10/11 |

### System Requirements

- **macOS**: 11.0+ (Big Sur or later)
- **Windows**: Windows 10 64-bit or later
- No additional Ghostscript installation required (bundled)

---

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask, Werkzeug
- **Compression Engine**: Ghostscript 10.x
- **Frontend**: Vanilla JS, CSS3
- **Packaging**: PyInstaller 6.x
- **CI/CD**: GitHub Actions

---

## ☕ Support the Author

If this project helped you, buying me a coffee would mean the world — it keeps me motivated to maintain it.

<p align="center">
  <b>Join Community</b><br><br>
  <img src="docs/images/wechat-group.png" width="200" alt="WeChat Group QR Code"><br><br>
  <i>Share tips, report issues, discuss compression techniques</i>
</p>

> 💡 **If the group QR code expired**, scan "Add Me on WeChat" below, message "PDF", and I'll add you.

<p align="center">
  <b>Add Me on WeChat</b><br><br>
  <img src="docs/images/wechat-personal.png" width="200" alt="WeChat Personal QR Code">
</p>

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

### Development

```bash
# Clone the repo
git clone https://github.com/kkxwz/PDFCompressor.git
cd PDFCompressor

# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py
```

### Build

```bash
# macOS
bash scripts/build_mac.sh

# Windows
scripts\build_windows.bat
```

---

## 📜 License

[MIT](LICENSE) © [shaonaiyi@163.com](mailto:shaonaiyi@163.com)

---

<p align="center">
  <i>Made with ❤️ for the people who matter most.</i>
</p>
