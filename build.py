import os
import subprocess
import requests
import re
import time
import psutil
import json
import logging
import threading

# Telegram settings
CHAT_ID = "0000000000"
BOT_TOKEN = "0000000000:0000000000aLPb6Yn2xCmCLS5EBh_qGBsM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Build settings
LUNCH_TARGET = "aosp_device-ap4a-user"
BUILD_TARGET = "bacon"

# Pixeldrain settings
BASE_URL = "https://pixeldrain.com/api"
FILE_URL = "https://pixeldrain.com"
API_KEY = "00000000-00000-0000-0000-0000000000"


# Functions to send messages to Telegram
def send_telegram_message(message):
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, data=data)
        return response.json().get("result", {}).get("message_id")
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")

def edit_telegram_message(message_id, new_text):
    try:
        url = f"{TELEGRAM_API_URL}/editMessageText"
        data = {
            "chat_id": CHAT_ID,
            "message_id": message_id,
            "text": new_text,
            "parse_mode": "HTML",
        }
        requests.post(url, data=data)
    except Exception as e:
        logging.error(f"Error editing message on Telegram: {e}")

def send_telegram_file(file_path, caption=""):
    try:
        url = f"{TELEGRAM_API_URL}/sendDocument"
        with open(file_path, "rb") as file:
            data = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"}
            files = {"document": file}
            requests.post(url, data=data, files=files)
    except Exception as e:
        logging.error(f"Error sending file to Telegram: {e}")

# Get information about the ROM and device
def get_rom_info():
    process = subprocess.run(
        f"source build/envsetup.sh && lunch {LUNCH_TARGET}",
        shell=True,
        executable="/bin/bash",
        capture_output=True,
        text=True,
    )
    output = process.stdout
    rom_info = re.search(r"CUSTOM_VERSION=([\w\-.]+)", output)
    android_version = re.search(r"PLATFORM_VERSION=([\d.]+)", output)
    device = re.search(r"TARGET_PRODUCT=(\w+)", output)

    rom = rom_info.group(1) if rom_info else "Unknown"
    version = android_version.group(1) if android_version else "Unknown"
    device_name = device.group(1).split("_")[1] if device else "Unknown"

    return rom, version, device_name

# Function to start the build process
def start_build():
    build_command = f"source build/envsetup.sh && lunch {LUNCH_TARGET} && make {BUILD_TARGET} -j$(nproc)"
    log_file = "build.log"

    with open(log_file, "w") as log:
        build_process = subprocess.Popen(
            build_command,
            shell=True,
            executable="/bin/bash",
            stdout=log,
            stderr=log
        )

    return build_process, log_file

# Capture system resource usage
def get_system_resources():
    try:
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "cpu": f"{cpu_usage}%",
            "ram": f"{memory.percent}%",
            "disk": f"{disk.used // (1024 ** 3)}GB/{disk.total // (1024 ** 3)}GB ({disk.percent}%)"
        }
    except Exception as e:
        logging.error(f"Error monitoring system resources: {e}")
        return {"cpu": "N/A", "ram": "N/A", "disk": "N/A"}

# Monitor build progress and send updates to Telegram
def monitor_build_progress(log_file, message_id, rom, version, device_name):
    progress_pattern = re.compile(r"\[\s*(\d+)%\s+(\d+/\d+)\s+([\d\w]+ remaining)\]")  # Capture detailed progress
    previous_progress = None
    try:
        with open(log_file, "r") as log:
            while True:
                line = log.readline()
                if not line:
                    time.sleep(1)
                    continue
                match = progress_pattern.search(line)
                if match:
                    percentage = match.group(1) + "%"  # Example: "88%"
                    tasks = match.group(2)  # Example: "104/118"
                    time_remaining = match.group(3)  # Example: "5m49s remaining"
                    progress = f"{percentage} {tasks} {time_remaining}"
                    if progress != previous_progress:
                        # Monitor system resources
                        resources = get_system_resources()
                        cpu = resources["cpu"]
                        ram = resources["ram"]
                        disk = resources["disk"]

                        # Update message on Telegram
                        new_text = (
                            f"🔄 <b>Compiling...</b>\n"
                            f"<b>ROM:</b> {rom}\n"
                            f"<b>Android:</b> {version}\n"
                            f"<b>Device:</b> {device_name}\n"
                            f"<b>Progress:</b> {progress}\n"
                            f"<b>System Resources:</b>\n"
                            f"• CPU: {cpu}\n"
                            f"• RAM: {ram}\n"
                            f"• Disk: {disk}"
                        )
                        edit_telegram_message(message_id, new_text)
                        previous_progress = progress
                if "ota_from_target_files.py - INFO    : done" in line:
                    break
    except Exception as e:
        logging.error(f"Error monitoring progress: {e}")

# Pixeldrain API
def upload_file_to_pixeldrain(rom_path, API_KEY):
    url = "https://pixeldrain.com/api/file/"

    try:
        result = subprocess.run(
            ["curl", "-T", rom_path, "-u", f":{API_KEY}", "--retry", "3", url],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logging.error(f"Error uploading to Pixeldrain: {result.stderr}")
            return None

        response_data = json.loads(result.stdout)
        logging.info(f"Pixeldrain API response: {response_data}")  # Add this print for debugging
        file_id = response_data.get("id")

        if file_id:
            return f"https://pixeldrain.com/u/{file_id}"
        else:
            logging.error("Error: Could not get file ID from Pixeldrain.")
            return None

    except FileNotFoundError:
        logging.error(f"Error: File '{rom_path}' not found.")
        return None
    except Exception as e:
        logging.error(f"Error uploading to Pixeldrain: {e}")
        return None

# Upload the compiled ROM
def upload_build(device_name, rom, log_file):
    # Get the file path
    rom_path = None
    with open(log_file, "r") as log:
      line = next((line for line in log if re.search(rf"Package Complete: (out/target/product/{device_name}/[\w\-\.]+\.zip)", line)), None)
      if line:
           rom_path = re.search(rf"Package Complete: (out/target/product/{device_name}/[\w\-\.]+\.zip)", line).group(1)

    # Get file size in MB
    file_size_mb = round(os.path.getsize(rom_path) / (1024 ** 2), 2)

    # Inform the start of the upload
    upload_message_id = send_telegram_message(
        f"🟡 <b>Starting upload...!</b>\n"
        f"<b>ROM:</b> {rom}\n"
        f"<b>File size:</b> {file_size_mb} MB\n"
        f"<b>Device:</b> {device_name}",
    )

    # Check if the ROM file exists
    if not os.path.exists(rom_path):
        logging.error(f"Error: ROM file '{rom_path}' not found.")
        edit_telegram_message(
            upload_message_id,
            f"🔴 <b>Upload failed: ROM file not found!</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>File size:</b> {file_size_mb} MB\n"
            f"<b>Device:</b> {device_name}",
        )
        return False

    # Upload the ROM file to Pixeldrain
    file_url = upload_file_to_pixeldrain(rom_path, API_KEY)

    # Check if the upload was successful
    if file_url:
        edit_telegram_message(
            upload_message_id,
            f"🟢 <b>Upload completed successfully!</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>File size:</b> {file_size_mb} MB\n"
            f"<b>Device:</b> {device_name}\n"
            f"☁️ <a href='{file_url}'>Download</a>",
        )
        return True
    else:
        logging.error("Error: Failed to upload the file.")
        edit_telegram_message(
            upload_message_id,
            f"🔴 <b>Upload failed: failed to upload the file!</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>File size:</b> {file_size_mb} MB\n"
            f"<b>Device:</b> {device_name}",
        )
        return False

# Main function
def main():
    log_file = None  # Initialize with None to avoid reference errors
    try:
        # Start lunch and get information about the ROM/device
        rom, version, device_name = get_rom_info()

        # Send initial message and get the message ID
        message_id = send_telegram_message(
            f"🟡 <b>Starting compilation...</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>Android:</b> {version}\n"
            f"<b>Device:</b> {device_name}\n"
            f"<b>Progress:</b> 0%"
        )

        # Start the build and monitor the progress in parallel
        build_process, log_file = start_build()

        # Create a thread to monitor the progress
        monitor_thread = threading.Thread(
            target=monitor_build_progress,
            args=(log_file, message_id, rom, version, device_name)
        )
        monitor_thread.start()

        # Wait for the build to complete
        build_process.wait()

        # Check the build result
        if build_process.returncode == 0:
            edit_telegram_message(
                message_id,
                f"🟢 <b>Compilation completed successfully!</b>\n"
                f"<b>ROM:</b> {rom}\n"
                f"<b>Android:</b> {version}\n"
                f"<b>Device:</b> {device_name}",
            )
            time.sleep(5)  # Wait 5 seconds before uploading
            upload_build(device_name, rom, log_file)
        else:
            edit_telegram_message(message_id, "🔴 <b>Compilation failed!</b>")
            send_telegram_file(log_file, "🔴 <b>Error log:</b>")

        # Wait for the monitoring thread to finish (optional)
        monitor_thread.join()

    except Exception as e:
        send_telegram_message(f"🔴 <b>Unexpected error:</b> {str(e)}")
    finally:
        # Check if log_file is defined and exists before using it
        if log_file and os.path.exists(log_file):
            send_telegram_file(log_file, "📄 <b>Final log:</b>")
            os.remove(log_file)

if __name__ == "__main__":
    main()