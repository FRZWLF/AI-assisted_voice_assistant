from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from loguru import logger
import global_variables
import geocoder


class ActionLocation(Action):

    def name(self):
        return "action_location"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain):
        # Sprache aus globalen Variablen
        LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

        # Ermittle Standort mittels IP
        loc = geocoder.ip('me')
        if loc and loc.city:
            city = loc.city if loc.city else "an unknown location"
            return [SlotSet("location", city)]
        else:
            # Wenn der Standort nicht ermittelt werden kann, gib eine Fehlermeldung aus
            if LANGUAGE == "de":
                dispatcher.utter_message(text="Standort konnte nicht bestimmt werden.")
            else:
                dispatcher.utter_message(text="Location could not be determined.")
            return []







    # config_path = os.path.join('intents','functions','location','config_location.yml')
    # cfg = None
    #
    # with open(config_path, "r", encoding='utf8') as ymlfile:
    #     cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    #
    # if not cfg:
    #     logger.error("Konnte Konfigurationsdatei für die Lokalisierung nicht lesen.")
    #     return ""
    #
    # # Holen der Sprache aus der globalen Konfigurationsdatei
    # LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']
    #
    # YOU_ARE_HERE = random.choice(cfg['intent']['location'][LANGUAGE]['youarehere'])
    #
    # # Ermittle den Standort mittels IP
    # loc = geocoder.ip('me')
    # return random.choice(YOU_ARE_HERE).format(loc.city)