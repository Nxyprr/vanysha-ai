#!/bin/bash
# Doble clic en Mac (o "bash INICIAR_MAC_LINUX.command" en Linux)
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "No encuentro Python 3. Instalalo desde https://www.python.org/downloads/ y vuelve a abrir este archivo."
  read -r -p "Pulsa Enter para cerrar..." _
  exit 1
fi
python3 start.py
echo
read -r -p "Pulsa Enter para cerrar..." _
