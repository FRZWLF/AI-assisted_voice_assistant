import glob
import importlib
import importlib.util
import os
import random
import sys
from pathlib import Path
from loguru import logger
import pip
from chatbot import Chat, mapper

import constants
import global_variables

class Chat(Chat):

    def get_intent_name(self,text,session_id="general"):
        session = mapper.Session(self,session_id)
        text = self.__normalize(text)

        try:
            previous_text = self.__normalize(session.conversation.get_bot_message(-1))
        except IndexError:
            previous_text = ""

        text_correction = self.spell_checker.correction(text)
        current_topic = session.topic
        match = self.__intend_selection(text, previous_text,current_topic) or self.__intend_selection(text_correction,previous_text,current_topic)

        if match:
            match,parent_match,response,learn = match
            resp = random.choice(response)
            response,condition = resp
            action_start = response.find("{% call ")
            action_end = response.find("%}")
            if action_start >=0 and action_end >=0:
                action_corpus = response[action_start + len("{% call "):action_end - 1]
                if action_corpus.find(":") > 0:
                    action_name = action_corpus.split(':')[0]
                    return action_name

        return ""


class IntentManagement:
    intent_count = 0

    def install(self, package):
        if hasattr(pip, 'main'):
            pip.main(['install', package])
        else:
            pip._internal.main(['install', package])

    def install_requirements(self, filename):
        retcode = 0
        with open(filename, "r") as f:
            for line in f:
                pipcode = pip.main(['install', line.strip()])
                retcode = retcode or pipcode
        return retcode

    def get_count(self):
        return self.intent_count

    def __init__(self, language_manager):
        self.language_manager = language_manager
        self.language_data = self.language_manager.translations
        functions_path = constants.find_data_file("intents/functions")
        if not os.path.exists(functions_path):
            raise FileNotFoundError(f"Pfad nicht gefunden: {functions_path}")
        base_path = os.path.abspath(constants.find_data_file("intents"))
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
            logger.debug("Basis-Pfad hinzugefügt: {}", base_path)

        self.functions_folders = [os.path.join(functions_path, name)
                                  for name in os.listdir(functions_path)
                                  if os.path.isdir(os.path.join(functions_path, name))]
        logger.debug("Gefundene Ordner: {}", self.functions_folders)
        self.dynamic_intents = []

        # Templates initial verarbeiten
        self.process_templates()

        self.intent_count = 0
        for ff in self.functions_folders:
            logger.debug("Suche nach Funktionen in {}...", ff)
            req_file = os.path.join(ff, 'requirements.txt')
            if os.path.exists(req_file):
                install_res = self.install_requirements(req_file)
                if install_res == 0:
                    logger.debug("Abhängigkeiten für {} wurden erfolgreich installiert.", ff)

            intent_files = glob.glob(os.path.join(ff, 'intent_*.py'))
            for infi in intent_files:
                logger.debug("Lade Intent-Datei {}...", infi)

                folder_name = Path(ff).stem
                intent_name = Path(infi).stem
                module_name = f"intents.functions.{folder_name}.{intent_name}"
                module_path = os.path.join(ff, f"{intent_name}.py")

                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module  # Modul manuell in sys.modules registrieren
                    spec.loader.exec_module(module)
                    logger.debug("Modul erfolgreich importiert: {}", module_name)
                    self.dynamic_intents.append(folder_name)
                    self.intent_count += 1
                except Exception as e:
                    logger.error("Fehler beim Import von {}: {}", module_name, e)


    def process_templates(self):
        """
        Lädt und verarbeitet die Templates basierend auf der aktuellen Sprache.
        """
        logger.info("Initialisiere ChatbotAI...")
        chatbotai_files = glob.glob(os.path.join(constants.find_data_file("intents/chatbotai"), '*.template'))
        MERGED_FILE = constants.find_data_file('intents/chatbotai/_merger.template')

        with open(MERGED_FILE, 'w', encoding='utf-8') as outfile:
            for caf in chatbotai_files:
                if not Path(caf).name == Path(MERGED_FILE).name:
                    logger.debug("Verarbeite chatbotai Template {}...", Path(caf).name)
                    try:
                        # Lies die Datei im korrekten Encoding
                        with open(caf, 'r', encoding='utf-8') as infile:
                            content = infile.read()
                    except UnicodeDecodeError:
                        logger.warning(f"Fehler beim Lesen der Datei {caf} mit UTF-8. Versuche mit latin-1.")
                        with open(caf, 'r', encoding='latin-1') as infile:
                            content = infile.read()
                    logger.debug(f"Original-Template-Inhalt:\n{content}")
                    # Ersetze Platzhalter mit Werten aus der Sprachdatei
                    replaced_content = self.replace_placeholders(content, self.language_manager.translations)
                    logger.debug(f"Ersetzter Template-Inhalt:\n{replaced_content}")
                    outfile.write(replaced_content)
        logger.info(f"Templates verarbeitet und in {MERGED_FILE} gespeichert.")

        if os.path.isfile(MERGED_FILE):
            self.chat = Chat(MERGED_FILE)
        else:
            logger.error("Chatbotai konnte nicht initialisiert werden.")
            sys.exit(1)
        logger.info('Chatbot aus {} initialisiert.', MERGED_FILE)

    def replace_placeholders(self, template_content, data, parent_key=""):
        """
        Ersetzt Platzhalter im Template durch Werte aus der Sprachdatei.
        Unterstützt verschachtelte Keys und bietet Debugging-Logs.
        """
        for key, value in data.items():
            # Schlüssel erweitern für verschachtelte Werte
            full_key = f"{parent_key}.{key}" if parent_key else key

            if isinstance(value, dict):
                # Rekursiver Aufruf für verschachtelte Strukturen
                template_content = self.replace_placeholders(template_content, value, full_key)
            else:
                # Debugging: Überprüfen, welcher Platzhalter ersetzt wird
                placeholder = f"{{{{{full_key}}}}}"
                if placeholder in template_content:
                    logger.debug(f"Ersetze Platzhalter {placeholder} mit Wert: {value}")
                    template_content = template_content.replace(placeholder, str(value))
                else:
                    logger.warning(f"Platzhalter {placeholder} nicht im Template gefunden.")
        return template_content


    def register_callbacks(self):
        # Registriere alle Callback Funktionen
        logger.info("Registriere Callbacks...")
        callbacks = []
        for ff in self.functions_folders:
            module_name = "intents.functions." + Path(ff).name + ".intent_" + Path(ff).name
            module_obj = sys.modules[module_name]
            logger.debug("Verarbeite Modul {}...", module_name)
            if hasattr(module_obj, 'callback'):
                logger.debug("Callback in {} gefunden.", module_name)
                logger.info('Registriere Callback für {}.', module_name)
                callbacks.append(getattr(module_obj, 'callback'))
            else:
                logger.debug("{} hat kein Callback.", module_name)
        return callbacks


    def process(self,text,speaker):
        text = correct_recognition(text)
        intent_name = self.chat.get_intent_name(text)

        if global_variables.voice_assistant.user_management.authenticate_intent(speaker, intent_name):
            old_context = global_variables.context
            response = self.chat.respond(text)

            if not old_context is None:
                return global_variables.context(text)
            else:
                return response
        else:
            logger.info("Sprecher {} darf Intent {} nicht ausführen", speaker, intent_name)
            response = speaker + " darf den Befehl " + intent_name + " nicht ausführen."

        return response

def correct_recognition(text):
    """
    Korrigiert häufige Fehler bei der Spracherkennung. (needed for the weather intent in lang "en")
    """
    corrections = {
        "vedder": "weather",
        "vet er": "weather",
        "vet her": "weather",
        "whether": "weather",
        "veta": "weather",
    }
    for wrong, correct in corrections.items():
        if wrong in text.lower():
            text = text.lower().replace(wrong, correct)
    return text