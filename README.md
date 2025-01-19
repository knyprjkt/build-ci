# **Build-CI**
Este script automatiza o processo de compilação de ROMs Android, notificando progresso no Telegram e fazendo upload do arquivo final para o PixelDrain.

---

## Recursos suportados (por enquanto)
- Construir rom automaticamente
- Monitorar progresso e uso de recursos do sistema
- Fazer upload do arquivo final para o Pixeldrain
- Notificar todos os processos acima no telegram

---

## **Requisitos**
1. **Python 3.8+**
2. Dependências do sistema:
   - `curl` (para upload no PixelDrain)
3. Dependências Python:
   - Listadas no arquivo `requirements.txt`.

---

## **Instalação**
1. Faça o download manual dos arquivos diretamente a pasta home da sua rom:
   ```bash
   curl -O https://raw.githubusercontent.com/knyprjkt/build-ci/build.py
   curl -O https://raw.githubusercontent.com/knyprjkt/build-ci/requirements.txt
   ```
2. instale as dependências do python
   ```bash
   pip install -r requirements.txt
   '''

## **Como usar**
1. Apenas:
   ```bash
   python3 build.py
   ```
