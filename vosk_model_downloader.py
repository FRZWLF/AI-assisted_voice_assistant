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

class ProgressTracker:
    def __init__(self, total_size):
        self.total_size = total_size
        self.downloaded = 0
        self.lock = threading.Lock()

    def add_progress(self, chunk_size):
        with self.lock:
            self.downloaded += chunk_size
            self._validate_progress()

    def _validate_progress(self):
        if self.downloaded > self.total_size:
            #logger.warning("Fortschritt hat die Gesamtgröße überschritten. Begrenze auf 100%.")
            self.downloaded = self.total_size

    def get_percentage(self):
        return int((self.downloaded / self.total_size) * 100)


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


def download_chunk_with_retries(url, start, end, destination, index, progress_tracker, progress_callback, cancel_flag):
    """
    Lädt einen Chunk mit mehreren Versuchen herunter.
    """
    retries = 5
    backoff = 2  # Exponentieller Backoff (2 Sekunden, 4 Sekunden, ...)
    chunk_size = end - start + 1
    part_file = f"{destination}.part{index}"

    for attempt in range(retries):
        try:
            # Prüfen, ob die Datei teilweise existiert
            if os.path.exists(part_file) and os.path.getsize(part_file) == chunk_size:
                logger.info(f"Chunk {index} ist bereits vollständig heruntergeladen.")
                progress_tracker.add_progress(chunk_size)
                progress_callback(progress_tracker.get_percentage())
                return

            # Chunk herunterladen
            download_chunk(url, start, end, destination, index, progress_tracker, progress_callback, cancel_flag)
            progress_tracker.add_progress(chunk_size)
            progress_callback(progress_tracker.get_percentage())
            return  # Erfolgreicher Download
        except Exception as e:
            logger.error(f"Fehler beim Download von Chunk {index}, Versuch {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:  # Wartezeit vor nächstem Versuch
                time.sleep(backoff)
                backoff = min(backoff * 2, 70)
    raise RuntimeError(f"Chunk {index} konnte nach {retries} Versuchen nicht heruntergeladen werden.")


def validate_chunks(destination, num_chunks):
    """
    Überprüft, ob alle Chunks existieren und nicht leer sind.
    """
    for i in range(num_chunks):
        part_file = f"{destination}.part{i}"
        if not os.path.exists(part_file):
            logger.error(f"Teildatei fehlt: {part_file}")
            return False
        if os.path.getsize(part_file) == 0:
            logger.error(f"Teildatei ist leer: {part_file}")
            return False
    return True


zip_lock = threading.Lock()
def download_chunk(url, start, end, destination, index, progress_tracker, progress_callback, cancel_flag):
    """
    Lädt einen bestimmten Bereich (Chunk) der Datei herunter und aktualisiert den Fortschritt.
    """
    headers = {"Range": f"bytes={start}-{end}"}
    response = requests.get(url, headers=headers, stream=True)
    if response.status_code in (200, 206):  # 206 = Partial Content
        part_file = f"{destination}.part{index}"
        cancel_flag["temp_files"].append(part_file)
        with open(part_file, "wb") as f:
            downloaded_chunk_size = 0
            for chunk in response.iter_content(chunk_size=1024 * 1024):  # 1 MB Chunks
                if cancel_flag["cancel"]:  # Abbruch prüfen
                    logger.info(f"Abbruch erkannt in Thread {threading.current_thread().name}.")
                    return
                f.write(chunk)
                downloaded_chunk_size += len(chunk)
                progress_tracker.add_progress(len(chunk))  # Fortschritt aktualisieren
                progress_callback(progress_tracker.get_percentage())  # Prozent aktualisieren
        if downloaded_chunk_size != (end - start + 1):
            logger.warning(f"Chunk {index} wurde nicht vollständig heruntergeladen.")
    else:
        raise ValueError(f"Failed to download chunk {index}: {response.status_code}")

def merge_chunks(destination, num_chunks):
    """
    Fügt heruntergeladene Teile zu einer Datei zusammen.
    """
    attempt = 0
    retry_limit = 3
    while attempt < retry_limit:
        if validate_chunks(destination, num_chunks):
            try:
                logger.info(f"Starte Zusammenfügen der Teildateien für {destination}, Versuch {attempt + 1} von {retry_limit}...")
                with zip_lock, open(destination, "wb") as output_file:
                    for i in range(num_chunks):
                        part_file = f"{destination}.part{i}"
                        if not os.path.exists(part_file):
                            logger.error(f"Teildatei fehlt: {part_file}")
                            continue
                        if os.path.getsize(part_file) == 0:
                            logger.error(f"Teildatei ist leer: {part_file}")
                            continue
                        with open(part_file, "rb") as f:
                            output_file.write(f.read())
                        os.remove(part_file)  # Lösche den Teil nach dem Zusammenführen
                        logger.info(f"Teildatei gelöscht: {part_file}")

                # Validierung der fertigen ZIP-Datei
                with ZipFile(destination, "r") as zip_ref:
                    if zip_ref.testzip():
                        logger.error(f"Defekte ZIP-Datei: {destination}")
                        os.remove(destination)  # Lösche die ungültige Datei
                        raise ValueError(f"Defekte ZIP-Datei: {destination}")
                logger.info(f"ZIP-Datei erfolgreich zusammengefügt und validiert: {destination}")
                return True  # Erfolgreich beendet
            except Exception as e:
                logger.error(f"Fehler beim Zusammenfügen der Teildateien oder Validieren der ZIP-Datei: {e}")
                if os.path.exists(destination):
                    os.remove(destination)  # Lösche ungültige ZIP-Datei
        else:
            logger.error(f"Teildateien sind nicht valide, Versuch {attempt + 1}/{retry_limit}")
        attempt += 1
    logger.error(f"Nach {retry_limit} Versuchen konnte die ZIP-Datei {destination} nicht korrekt zusammengefügt werden.")
    return False


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


def download_file_with_progress(url, destination, language, progress_tracker, progress_callback, num_threads=4, cancel_flag=None):
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
    progress_tracker.total_size = total_size
    # Fortschrittsdaten initialisieren
    progress_data = {"total": total_size, "downloaded": 0, "threads_cancelled": 0}

    threads = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i, (start, end) in enumerate(ranges):
            if cancel_flag["cancel"]:
                logger.info("Abbruch erkannt. Keine weiteren Downloads starten.")
                progress_data["threads_cancelled"] += 1
                break
            thread = executor.submit(download_chunk_with_retries, url, start, end, destination, i, progress_tracker, progress_callback, cancel_flag)
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
        _validate_and_finalize_progress(progress_tracker, destination, total_size, num_threads, progress_callback)
        merge_chunks(destination, num_chunks=num_threads)
        logger.info(f"Download abgeschlossen: {destination}")
        progress_callback(progress_tracker.get_percentage())
    else:
        logger.info("Download abgebrochen. Temporäre Dateien werden bereinigt.")


def _validate_and_finalize_progress(progress_tracker, destination, total_size, num_chunks, progress_callback):
    """
    Validiert den Fortschritt und korrigiert fehlende Prozente nach Abschluss des Downloads.
    """
    downloaded_size = sum(
        os.path.getsize(f"{destination}.part{i}")
        for i in range(num_chunks)
        if os.path.exists(f"{destination}.part{i}")
    )
    with progress_tracker.lock:
        progress_tracker.downloaded = downloaded_size
        if progress_tracker.downloaded < total_size:
            #logger.info(f"Fehlender Fortschritt wird korrigiert: {total_size - progress_tracker.downloaded} Bytes.")
            progress_tracker.downloaded = total_size
        progress_callback(progress_tracker.get_percentage())


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
    potential_dirs = [
        p for p in model_dir_pattern.parent.glob(model_dir_pattern.name)
        if p.is_dir()  # Prüfe, ob es ein Verzeichnis ist
    ]
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
        response = requests.head(url)
        total_size = int(response.headers.get("Content-Length", 0))
        progress_tracker = ProgressTracker(total_size)

        def progress_callback(percent):
            app.update_progress(language, progress_tracker.get_percentage())  # Fortschritt an die App melden

        download_file_with_progress(url, zip_file, language, progress_tracker, progress_callback, cancel_flag=app.cancel_flag)

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
        logger.info(f"Prüfe ZIP-Datei: {zip_file}")
        if not zip_file.exists():
            logger.error(f"ZIP-Datei fehlt: {zip_file}")
            return False

        if zip_file.stat().st_size == 0:
            logger.error(f"ZIP-Datei ist leer: {zip_file}")
            return False

        destination_path = Path(destination)
        destination_path.mkdir(parents=True, exist_ok=True)

        if not os.access(destination, os.W_OK):
            logger.error(f"Keine Schreibrechte für Zielverzeichnis: {destination}")
            return False

        with ZipFile(zip_file, "r") as zip_ref:
            bad_file = zip_ref.testzip()
            if bad_file:
                logger.error(f"Defekte Datei in ZIP gefunden: {bad_file}")
                return False

            for file in zip_ref.namelist():
                logger.info(f"Prüfe Datei in ZIP: {file}")
                if ":" in file or len(file) > 255:
                    logger.error(f"Ungültiger Dateiname in ZIP: {file}")
                    return False

            zip_ref.extractall(destination)
        logger.info(f"Extraktion von {zip_file} abgeschlossen.")
    except OSError as e:
        logger.error(f"OSError beim Extrahieren von {zip_file}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Extrahieren von {zip_file}: {e}")
        try:
            zip_file.unlink()
            logger.info(f"Fehlerhafte ZIP-Datei gelöscht: {zip_file}")
        except Exception as cleanup_error:
            logger.error(f"Fehler beim Löschen der ZIP-Datei {zip_file}: {cleanup_error}")
        return False
    return True