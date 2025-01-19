import os
import subprocess
import requests
import re
import time
import psutil
import json
import logging
import threading

# Configurações do Telegram
CHAT_ID = "0000000000"
BOT_TOKEN = "0000000000:0000000000aLPb6Yn2xCmCLS5EBh_qGBsM"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Configurações de build
LUNCH_TARGET = "aosp_device-ap4a-user"
BUILD_TARGET = "bacon"

# Configurações do Pixeldrain
BASE_URL = "https://pixeldrain.com/api"
FILE_URL = "https://pixeldrain.com"
API_KEY = "00000000-00000-0000-0000-0000000000"


# Funções para envio de mensagens ao Telegram
def send_telegram_message(message):
    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, data=data)
        return response.json().get("result", {}).get("message_id")
    except Exception as e:
        logging.error(f"Erro ao enviar mensagem ao Telegram: {e}")

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
        logging.error(f"Erro ao editar mensagem no Telegram: {e}")

def send_telegram_file(file_path, caption=""):
    try:
        url = f"{TELEGRAM_API_URL}/sendDocument"
        with open(file_path, "rb") as file:
            data = {"chat_id": CHAT_ID, "caption": caption}
            files = {"document": file}
            requests.post(url, data=data, files=files)
    except Exception as e:
        logging.error(f"Erro ao enviar arquivo ao Telegram: {e}")

# Pegar infromações sobre a ROM e device
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

    rom = rom_info.group(1) if rom_info else "Desconhecido"
    version = android_version.group(1) if android_version else "Desconhecido"
    device_name = device.group(1).split("_")[1] if device else "Desconhecido"

    return rom, version, device_name

# Função para iniciar o processo de build
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

# Capturar uso de recursos do sistema
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
        logging.error(f"Erro ao monitorar recursos do sistema: {e}")
        return {"cpu": "N/A", "ram": "N/A", "disk": "N/A"}

# Monitorar progresso do build e enviar para o telegram
def monitor_build_progress(log_file, message_id, rom, version, device_name):
    progress_pattern = re.compile(r"\[\s*(\d+)%\s+(\d+/\d+)\s+([\d\w]+ remaining)\]")  # Captura progresso detalhado
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
                    percentage = match.group(1) + "%"  # Exemplo: "88%"
                    tasks = match.group(2)  # Exemplo: "104/118"
                    time_remaining = match.group(3)  # Exemplo: "5m49s remaining"
                    progress = f"{percentage} {tasks} {time_remaining}"
                    if progress != previous_progress:
                        # Monitorar recursos do sistema
                        resources = get_system_resources()
                        cpu = resources["cpu"]
                        ram = resources["ram"]
                        disk = resources["disk"]

                        # Atualizar mensagem no Telegram
                        new_text = (
                            f"🔄 <b>Compilando...</b>\n"
                            f"<b>ROM:</b> {rom}\n"
                            f"<b>Android:</b> {version}\n"
                            f"<b>Dispositivo:</b> {device_name}\n"
                            f"<b>Progresso:</b> {progress}\n"
                            f"<b>Recursos do Sistema:</b>\n"
                            f"• CPU: {cpu}\n"
                            f"• RAM: {ram}\n"
                            f"• Disco: {disk}"
                        )
                        edit_telegram_message(message_id, new_text)
                        previous_progress = progress
                if "ota_from_target_files.py - INFO    : done" in line:
                    break
    except Exception as e:
        logging.error(f"Erro ao monitorar progresso: {e}")

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
            logging.error(f"Erro ao fazer upload para o Pixeldrain: {result.stderr}")
            return None

        response_data = json.loads(result.stdout)
        logging.info(f"Resposta da API do Pixeldrain: {response_data}")  # Adicionar este print para depuração
        file_id = response_data.get("id")

        if file_id:
            return f"https://pixeldrain.com/u/{file_id}"
        else:
            logging.error("Erro: Não foi possível obter o ID do arquivo do Pixeldrain.")
            return None

    except FileNotFoundError:
        logging.error(f"Erro: O arquivo '{rom_path}' não foi encontrado.")
        return None
    except Exception as e:
        logging.error(f"Erro ao fazer upload para o Pixeldrain: {e}")
        return None

# Fazer upload da ROM compilada
def upload_build(device_name, rom, log_file):
    # Obter path do arquivo
    rom_path = None
    with open(log_file, "r") as log:
      line = next((line for line in log if re.search(rf"Package Complete: (out/target/product/{device_name}/[\w\-\.]+\.zip)", line)), None)
      if line:
           rom_path = re.search(rf"Package Complete: (out/target/product/{device_name}/[\w\-\.]+\.zip)", line).group(1)

    # Guardar tamanho do arquivo em MB
    file_size_mb = round(os.path.getsize(rom_path) / (1024 ** 2), 2)

    # Informar início do upload
    upload_message_id = send_telegram_message(
        f"🟡 <b>Iniciando upload...!</b>\n"
        f"<b>ROM:</b> {rom}\n"
        f"<b>Tamanho do arquivo:</b> {file_size_mb} MB\n"
        f"<b>Dispositivo:</b> {device_name}",
    )

    # Verificar se o arquivo ROM existe
    if not os.path.exists(rom_path):
        logging.error(f"Erro: O arquivo ROM '{rom_path}' não foi encontrado.")
        edit_telegram_message(
            upload_message_id,
            f"🔴 <b>Falha no upload: arquivo ROM não encontrado!</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>Tamanho do arquivo:</b> {file_size_mb} MB\n"
            f"<b>Dispositivo:</b> {device_name}",
        )
        return False

    # Fazer upload do arquivo ROM para o Pixeldrain
    file_url = upload_file_to_pixeldrain(rom_path, API_KEY)

    # Verificar se o upload foi bem-sucedido
    if file_url:
        edit_telegram_message(
            upload_message_id,
            f"🟢 <b>Upload concluído com sucesso!</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>Tamanho do arquivo:</b> {file_size_mb} MB\n"
            f"<b>Dispositivo:</b> {device_name}\n"
            f"☁️ <a href='{file_url}'>Download</a>",
        )
        return True
    else:
        logging.error("Erro: Falha ao fazer upload do arquivo.")
        edit_telegram_message(
            upload_message_id,
            f"🔴 <b>Falha no upload: falha ao fazer upload do arquivo!</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>Tamanho do arquivo:</b> {file_size_mb} MB\n"
            f"<b>Dispositivo:</b> {device_name}",
        )
        return False

# Função principal
def main():
    log_file = None  # Inicialize com None para evitar erros de referência
    try:
        # Iniciar lunch e obter informações sobre a ROM/device
        rom, version, device_name = get_rom_info()

        # Enviar mensagem inicial e obter o ID da mensagem
        message_id = send_telegram_message(
            f"🟡 <b>Iniciando compilação...</b>\n"
            f"<b>ROM:</b> {rom}\n"
            f"<b>Android:</b> {version}\n"
            f"<b>Dispositivo:</b> {device_name}\n"
            f"<b>Progresso:</b> 0%"
        )

        # Iniciar o build e monitorar o progresso em paralelo
        build_process, log_file = start_build()

        # Criar uma thread para monitorar o progresso
        monitor_thread = threading.Thread(
            target=monitor_build_progress,
            args=(log_file, message_id, rom, version, device_name)
        )
        monitor_thread.start()

        # Aguardar conclusão do build
        build_process.wait()

        # Verificar resultado do build
        if build_process.returncode == 0:
            edit_telegram_message(
                message_id,
                f"🟢 <b>Compilação concluída com sucesso!</b>\n"
                f"<b>ROM:</b> {rom}\n"
                f"<b>Android:</b> {version}\n"
                f"<b>Dispositivo:</b> {device_name}",
            )
            time.sleep(5)  # Aguardar 5 segundos antes de fazer upload
            upload_build(device_name, rom, log_file)
        else:
            edit_telegram_message(message_id, "🔴 <b>Compilação falhou!</b>")
            send_telegram_file(log_file, "🔴 <b>Log de erro:</b>")

        # Aguarde o término da thread de monitoramento (opcional)
        monitor_thread.join()

    except Exception as e:
        send_telegram_message(f"🔴 <b>Erro inesperado:</b> {str(e)}")
    finally:
        # Verifique se log_file foi definido e existe antes de usá-lo
        if log_file and os.path.exists(log_file):
            send_telegram_file(log_file, "📄 <b>Log final:</b>")
            os.remove(log_file)

if __name__ == "__main__":
    main()