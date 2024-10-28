#!/bin/bash

# Beispiel: Lade Dateien von Google Drive herunter
echo "Downloading large model files..."

# Ersetze <google_drive_link> mit dem tatsächlichen Link zur Datei
curl -L -o vosk-model-de-0.21.zip "<https://drive.google.com/drive/folders/1TnyGgdWiGsmpyeT8ShPB114RS4k_Iv6m?usp=drive_link>"

# Entpacke, wenn notwendig
unzip vosk-model-de-0.21.zip -d vosk-model-de-0.21

echo "Download and extraction completed."
