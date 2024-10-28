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

    def __init__(self):

        self.functions_folders = [os.path.abspath(name) for name in glob.glob("./intents/functions/*/")]
        self.dynamic_intents = []

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

                name = infi.strip('.py')
                name = "intents.functions." + Path(ff).name + ".intent_" + Path(ff).name
                name = name.replace(os.path.sep, ".")

                logger.debug("Importiere modul {}...", name)
                globals()[Path(ff).name] = importlib.import_module(name)
                logger.debug("Modul {} geladen.", str(Path(ff).name))
                self.dynamic_intents.append(str(Path(ff).name))
                self.intent_count += 1

        logger.info("Initialisiere ChatbotAI...")
        chatbotai_files = glob.glob(os.path.join("./intents/chatbotai", "*.template"))
        MERGED_FILE = "./intents/chatbotai/_merger.template"

        with open(MERGED_FILE, 'w') as outfile:
            for caf in chatbotai_files:
                if not Path(caf).name == Path(MERGED_FILE).name:
                    logger.debug("Verarbeite chatbotai Template {}...", Path(caf).name)
                    with open(caf) as infile:
                        outfile.write(infile.read())

        if os.path.isfile(MERGED_FILE):
            self.chat = Chat(MERGED_FILE)
        else:
            logger.error("Chatbotai konnte nicht initialisiert werden.")
            sys.exit(1)
        logger.info('Chatbot aus {} initialisiert.', MERGED_FILE)

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