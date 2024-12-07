import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from glob import glob
from pathlib import Path
import requests
from zipfile import ZipFile
from loguru import logger

from constants import find_data_file
from download_app import DownloadApp

# Basisverzeichnis für Vosk-Modelle
BASE_MODEL_DIR = find_data_file("vosk_models")

# Verfügbare Vosk-Modelle und URLs
VOSK_MODELS = {
    "en": "https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip",
    "de": "https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip",
    "fr": "https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip",
    "es": "https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip",
    "it": "https://alphacephei.com/vosk/models/vosk-model-it-0.22.zip",
    "ja": "https://alphacephei.com/vosk/models/vosk-model-ja-0.22.zip",
    "ru": "https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip",
    "spk": "https://alphacephei.com/vosk/models/vosk-model-spk-0.4.zip"
}

def download_chunk(url, start, end, destination, index, progress_callback, cancel_flag):
    """
    Lädt einen bestimmten Bereich (Chunk) der Datei herunter und aktualisiert den Fortschritt.
    """
    headers = {"Range": f"bytes={start}-{end}"}
    response = requests.get(url, headers=headers, stream=True)
    if response.status_code in (200, 206):  # 206 = Partial Content
        part_file = f"{destination}.part{index}"
        cancel_flag["temp_files"].append(part_file)
        with open(part_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB Chunks
                if cancel_flag["cancel"]:  # Abbruch prüfen
                    logger.info(f"Abbruch erkannt in Thread {threading.current_thread().name}.")
                    return
                f.write(chunk)
                progress_callback(len(chunk))  # Fortschritt melden
    else:
        raise ValueError(f"Failed to download chunk {index}: {response.status_code}")

def merge_chunks(destination, num_chunks):
    """
    Fügt heruntergeladene Teile zu einer Datei zusammen.
    """
    with open(destination, "wb") as output_file:
        for i in range(num_chunks):
            part_file = f"{destination}.part{i}"
            with open(part_file, "rb") as f:
                output_file.write(f.read())
            os.remove(part_file)  # Lösche den Teil nach dem Zusammenführen


def download_all_vosk_models(skip_language=None, app=None):
    """
    Downloads all Vosk models except the one specified in skip_language in parallel.
    """
    if app is None:
        raise ValueError("DownloadApp instance is required.")

    threads = []
    for lang, url in VOSK_MODELS.items():
        if lang == skip_language:
            continue
        thread = threading.Thread(target=download_vosk_model, args=(lang, app), name=f"download-{lang}")
        thread.daemon = True
        thread.start()
        threads.append(thread)

    for thread in threads:
        if app.cancel_flag["cancel"]:
            logger.info("Abbruchsignal empfangen. Beende Threads...")
            break
        thread.join()

    print("All models downloaded.")


def download_file_with_progress(url, destination, language, progress_callback, num_threads=4, cancel_flag=None):
    if cancel_flag is None:
        raise ValueError("cancel_flag muss übergeben werden!")

    response = requests.head(url)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch file information: {response.status_code}")

    total_size = int(response.headers.get("Content-Length", 0))
    chunk_size = total_size // num_threads
    ranges = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(num_threads)]
    ranges[-1] = (ranges[-1][0], total_size - 1)  # Letzter Block bis zum Ende

    logger.info(f"Downloading {destination} with {num_threads} threads...")
    # Fortschrittsdaten initialisieren
    progress_data = {"total": total_size, "downloaded": 0, "threads_cancelled": 0}
    lock = threading.Lock()

    def update_progress(chunk_size):
        with lock:
            progress_data["downloaded"] += chunk_size
            progress_callback(progress_data["downloaded"], progress_data["total"])

    threads = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i, (start, end) in enumerate(ranges):
            if cancel_flag["cancel"]:
                logger.info("Abbruch erkannt. Keine weiteren Downloads starten.")
                progress_data["threads_cancelled"] += 1
                break
            thread = executor.submit(download_chunk, url, start, end, destination, i, update_progress, cancel_flag)
            threads.append(thread)

        # Überwache laufende Threads
        for thread in threads:
            while not thread.done():
                #logger.info(f"Warte auf Thread {thread}...")
                time.sleep(1)  # Verhindert Busy-Waiting
                if cancel_flag["cancel"]:
                    logger.warning(f"Thread {thread} wurde abgebrochen.")
                    break  # Beende die Warteschleife, falls abgebrochen

        executor.shutdown(wait=True)

    if not cancel_flag["cancel"]:
        merge_chunks(destination, num_threads)
        logger.info(f"Download abgeschlossen: {destination}")
        progress_callback(total_size, total_size)
    else:
        logger.info("Download abgebrochen. Temporäre Dateien werden bereinigt.")


def download_vosk_model(language: str, app: DownloadApp):
    """
    Downloads and extracts the Vosk model for the given language code.
    """
    if language not in VOSK_MODELS:
        raise ValueError(f"No model available for language: {language}")

    url = VOSK_MODELS[language]
    zip_file = Path(BASE_MODEL_DIR) / f"vosk-model-{language}.zip"
    model_dir_pattern = Path(BASE_MODEL_DIR) / f"vosk-model-{language}*"

    # Verzeichnisprüfung
    potential_dirs = list(model_dir_pattern.parent.glob(model_dir_pattern.name))
    if potential_dirs and any(Path(potential_dirs[0]).iterdir()):
        logger.info(f"Model for {language} already exists at {potential_dirs[0]}. Skipping download and extraction.")
        app.update_progress(language, 100)
        return str(potential_dirs[0])

    # ZIP-Prüfung
    if zip_file.exists():
        logger.info(f"ZIP file for {language} already exists at {zip_file}. Extracting...")
        if extract_zip_file(zip_file, BASE_MODEL_DIR):
            try:
                zip_file.unlink()  # Entferne ZIP nach erfolgreicher Extraktion
                logger.info(f"{zip_file} wurde erfolgreich gelöscht.")
            except Exception as e:
                logger.error(f"Fehler beim Löschen von {zip_file}: {e}")
        else:
            logger.error(f"Extraktion von {zip_file} für {language} fehlgeschlagen.")
        app.update_progress(language, 100)
        logger.info(f"Model for {language} ready at {potential_dirs[0]}.")
        return

    # Download, wenn weder Verzeichnis noch ZIP-Datei vorhanden sind
    if not potential_dirs and not zip_file.exists():
        logger.info(f"Downloading Vosk model for {language}...")
        def progress_callback(downloaded, total):
            percent = int((downloaded / total) * 100)
            app.update_progress(language, percent)  # Fortschritt an die App melden

        download_file_with_progress(url, zip_file, language, progress_callback, cancel_flag=app.cancel_flag)

        if app.cancel_flag["cancel"]:
            logger.info(f"Download für {language} abgebrochen. Temporäre Dateien werden bereinigt.")
            return

        # Extrahieren
        if not zip_file.exists():
            logger.error(f"Die Datei {zip_file} wurde nicht heruntergeladen. Überspringe das Extrahieren.")
            return

        logger.info(f"Extracting {zip_file}...")
        if extract_zip_file(zip_file, BASE_MODEL_DIR):
            try:
                zip_file.unlink()  # Entferne ZIP nach erfolgreicher Extraktion
            except FileNotFoundError as e:
                logger.error(f"Fehler beim Löschen von {zip_file}: {e}")
        else:
            logger.error(f"Extraktion von {zip_file} für {language} fehlgeschlagen.")

    potential_dirs = list(model_dir_pattern.parent.glob(model_dir_pattern.name))
    if potential_dirs:
        return str(potential_dirs[0])

    return str(potential_dirs[0])


def extract_zip_file(zip_file, destination):
    """
    Extrahiert eine ZIP-Datei in das Zielverzeichnis.
    """
    try:
        with ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(destination)
        logger.info(f"Extraktion von {zip_file} abgeschlossen.")
    except OSError as e:
        logger.error(f"Fehler beim Extrahieren von {zip_file}: {e}")
        return False
    return True