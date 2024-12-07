import sys
from cx_Freeze import setup, Executable
sys.setrecursionlimit(5000)
includefiles = ['config.yml', 'empty.wav', 'idle.png', 'initializing.png', 'listening.png', 'speaking.png', 'download_icon.png', 'users.json', 'va.ico', 'intents/', 'languages/', 'MarianMTModel/', 'vosk_models/']

build_exe_options = {"packages": ["pyttsx3.drivers.sapi5", "pip", "idna", "geocoder", "text2numde", "fuzzywuzzy", "dateutil", "pyowm", "wikipedia", "pip._vendor.distlib", "pip._internal.commands.install", "pykeepass", "pynput", "pytz", "scipy", "words2num", "num2words"], "excludes": [], "include_files": includefiles}

base = "Win32GUI"


bdist_msi_options = {
        "add_to_path": True,
        "install_icon": "va.ico",
        "summary_data": {"author": "Rico Richter"},
}

setup(  name = "Sprachassistent",
        version = "1.0",
        description = "Mein erster Sprachassistent",
        options = {
                "build_exe": build_exe_options, # 1. Schritt, dann ffmpeg und _soundfile_data kopieren
                "bdist_msi": bdist_msi_options # 2. Schritt (Schritt 1 auskommentieren, Schritt 2 einkommentieren)
        },
        executables = [Executable("main.py", base=base,icon="va.ico", shortcut_name="Sprachassistent",  shortcut_dir="DesktopFolder", uac_admin=True,)])