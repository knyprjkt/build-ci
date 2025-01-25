# **Build-CI**
This script automates the process of building Android ROMs, notifying progress on Telegram and uploading the final file to PixelDrain.

---

## Supported features (for now)
- Automatically build ROM
- Monitor progress and system resource usage
- Upload the final file to Pixeldrain
- Notify all the above processes on Telegram

---

## **Requirements**
1. **Python 3.8+**
2. System dependencies:
   - `curl` (for upload to PixelDrain)
3. Python dependencies:
   - Listed in the `requirements.txt` file.

---

## **Installation**
1. Manually download the files directly to your ROM's home folder:
   ```bash
   curl -O https://raw.githubusercontent.com/knyprjkt/build-ci/main/build.py
   curl -O https://raw.githubusercontent.com/knyprjkt/build-ci/main/requirements.txt