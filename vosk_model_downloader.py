import os
import threading
from pathlib import Path
import requests
from zipfile import ZipFile
from clint.textui import progress
from loguru import logger

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


def download_all_vosk_models(skip_language=None):
    """
    Downloads all Vosk models except the one specified in skip_language in parallel.
    """
    threads = []
    for lang, url in VOSK_MODELS.items():
        if lang == skip_language:
            continue
        thread = threading.Thread(target=download_vosk_model, args=(lang,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    print("All models downloaded.")


def download_file_with_progress(url, destination, language):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        total_length = int(response.headers.get('content-length', 0))
        with open(destination, "wb") as f:
            for chunk in progress.bar(
                    response.iter_content(chunk_size=1024),
                    expected_size=(total_length / 1024) + 1,
                    label=f"Downloading {destination}: "
            ):
                if chunk:
                    f.write(chunk)
                    f.flush()


def download_vosk_model(language: str):
    """
    Downloads and extracts the Vosk model for the given language code.
    """
    if language not in VOSK_MODELS:
        raise ValueError(f"No model available for language: {language}")

    url = VOSK_MODELS[language]
    model_dir = Path(f"./vosk-model-{language}")
    zip_file = Path(f"./vosk-model-{language}.zip")

    if os.path.exists(model_dir):
        print(f"Model for {language} already exists at {model_dir}.")
        return model_dir

    print(f"Downloading Vosk model for {language}...")
    download_file_with_progress(url, zip_file, language)
    print(f"Downloaded {zip_file}. Extracting...")
    with ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall("./")
    zip_file.unlink()  # Entferne ZIP nach dem Entpacken
    print(f"Model for {language} ready at {model_dir}.")

    if not model_dir.exists():
        # Suche nach dem Unterordner, falls der Entpackungspfad anders war
        potential_dirs = list(Path("./").glob(f"vosk-model-{language}*"))
        if potential_dirs:
            return str(potential_dirs[0])

    return str(model_dir)
