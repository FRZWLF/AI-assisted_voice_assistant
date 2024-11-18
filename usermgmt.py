from tinydb import TinyDB, Query

# Voice-Fingerabdruck muss unbedingt gefixt werden in zukünftigen Projekten
class UserMgmt:

    def init_first_user(self, name, fingerprint=None):
        Speaker = Query()
        # Prüfen, ob Benutzer vorhanden sind
        if not self.speaker_table.all():
            self.speaker_table.insert({'name': name, 'intents': ['*'], 'voice': fingerprint or []})
            return f"Benutzer {name} wurde als erster Nutzer hinzugefügt."
        return "Benutzer existieren bereits."

    def authenticate_intent(self,speaker,intent):
        Speaker = Query()

        result = self.speaker_table.get(Speaker.name == speaker)

        if not result is None:
            intents = result['intents']
            if intents:
                return ((len(intents) == 1) and (intents[0] == '*')) or (intent in intents)

        return False


    def __init__(self):
        self.db = TinyDB('./users.json')
        self.speaker_table = self.db.table('speakers')