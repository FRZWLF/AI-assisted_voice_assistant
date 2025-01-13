from loguru import logger
from tinydb import TinyDB, Query


# Voice-Fingerabdruck muss unbedingt gefixt werden in zukünftigen Projekten
class UserMgmt:

    def __add_sample_user__(self):
        if len(self.speaker_table) == 0:
            self.speaker_table.insert({'name': 'sample_user', 'intents': ['*'], 'voice': None})
            logger.info("Sample-User erstellt.")

    def authenticate_intent(self, speaker, intent):
        Speaker = Query()

        result = self.speaker_table.get(Speaker.name == speaker)

        if not result is None:
            intents = result['intents']
            if intents:
                return ((len(intents) == 1) and (intents[0] == '*')) or (intent in intents)

        return False

    def __init__(self, init_dummies=False):
        self.db = TinyDB('./users.json')
        self.speaker_table = self.db.table('speakers')

        if init_dummies:
            self.__add_sample_user__()
