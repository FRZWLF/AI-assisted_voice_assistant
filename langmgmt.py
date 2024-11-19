import yaml
import os

from loguru import logger

import global_variables


class LanguageManager:
    def __init__(self, language):
        self.language = language
        self.translations = {}
        self.load_language_file()

    def load_language_file(self):
        file_path = os.path.join("languages", f"{self.language}.yml")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                self.translations = yaml.safe_load(file)
            print(f"Sprachdatei '{file_path}' geladen.")
        else:
            print(f"Sprachdatei '{file_path}' nicht gefunden. Fallback auf Englisch.")
            self.language = "en"
            self.load_language_file()

    def reload_templates(self):
        """
        Löst das Neuladen und Verarbeiten der Templates aus.
        """
        global_variables.voice_assistant.intent_management.language_manager = self
        global_variables.voice_assistant.intent_management.process_templates()

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.translations
        try:
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            return default or f"[{key}]"

    def set_language(self, new_language):
        """
        Ändert die aktuelle Sprache und verarbeitet die Templates neu.
        """
        self.language = new_language
        self.load_language_file()
        self.reload_templates()
        logger.info(f"Sprache auf {new_language} geändert und Templates aktualisiert.")
