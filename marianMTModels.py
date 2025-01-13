from threading import Thread
from transformers import MarianMTModel, MarianTokenizer
from loguru import logger
import os
from typing import Sequence

import constants


def download_translation_models(model_dir="./MarianMTModel"):
    """
    Lädt MarianMT-Modelle für die Übersetzungen herunter, falls sie nicht vorhanden sind.
    """
    # Sprachpaare, die unterstützt werden sollen
    language_pairs = [
        ("de", "en"),  # Deutsch -> Englisch
        ("fr", "en"),  # Französisch -> Englisch
        ("es", "en"),  # Spanisch -> Englisch
        ("it", "en"),  # Italienisch -> Englisch
        ("ja", "en"),  # Japanisch -> Englisch
        ("ru", "en"),   # Russisch -> Englisch
        ("en", "de"),  # Englisch -> Deutsch
        ("en", "fr"),  # Englisch -> Französisch
        ("en", "es"),  # Englisch -> Spanisch
        ("en", "it"),  # Englisch -> Italienisch
        ("en", "jap"),  # Englisch -> Japanisch
        ("en", "ru"),   # Englisch -> Russisch
    ]

    def download_model(source_lang, target_lang, save_dir):
        """
        Lädt ein bestimmtes MarianMT-Modell herunter und speichert es lokal.
        """
        try:
            model_name = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"
            save_path = os.path.join(save_dir, f"opus-mt-{source_lang}-{target_lang}")
            if not os.path.exists(save_path):
                logger.info(f"Lade Modell {model_name} herunter...")
                os.makedirs(save_path, exist_ok=True)
                model = MarianMTModel.from_pretrained(model_name)
                tokenizer = MarianTokenizer.from_pretrained(model_name)
                model.save_pretrained(save_path)
                tokenizer.save_pretrained(save_path)
                logger.info(f"Modell {model_name} erfolgreich unter {save_path} gespeichert.")
            else:
                logger.info(f"Modell {model_name} ist bereits vorhanden. Überspringe Download.")
        except Exception as e:
            logger.error(f"Fehler beim Herunterladen des Modells {source_lang}->{target_lang}: {e}")

    # Hintergrund-Thread für den Download
    def download_all_models():
        logger.info("Prüfe auf fehlende Modelle...")
        for source, target in language_pairs:
            download_model(source, target, model_dir)
        logger.info("Alle Übersetzungsmodelle sind verfügbar.")

    # Starte den Download im Hintergrund
    thread = Thread(target=download_all_models)
    thread.daemon = True  # Hintergrundprozess, der das Programm nicht blockiert
    thread.start()


class Translator:
    def __init__(self, source_lang: str, dest_lang: str, model_dir="./MarianMTModel") -> None:
        if source_lang == dest_lang:
            self.is_identity_translation = True
            return

        self.is_identity_translation = False
        if dest_lang == "ja":
            dest_lang = "jap"

        self.model_name = f"opus-mt-{source_lang}-{dest_lang}"
        self.model_path = constants.find_data_file(os.path.join(model_dir, self.model_name))

        # Lade das Modell und den Tokenizer aus dem lokalen Verzeichnis
        self.model = MarianMTModel.from_pretrained(self.model_path, local_files_only=True)
        self.tokenizer = MarianTokenizer.from_pretrained(self.model_path, local_files_only=True)

    def translate(self, texts: Sequence[str]) -> Sequence[str]:
        if self.is_identity_translation:
            return texts

        # Falls texts ein einzelner String ist, wandle ihn in eine Liste um
        if isinstance(texts, str):
            texts = [texts]

        tokens = self.tokenizer(list(texts), return_tensors="pt", padding=True)
        translate_tokens = self.model.generate(**tokens)
        return [self.tokenizer.decode(t, skip_special_tokens=True) for t in translate_tokens]
