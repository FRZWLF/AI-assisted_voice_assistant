import os
import random
import numpy as np
import yaml
from chatbot import register_call
from loguru import logger
from tinydb import Query, TinyDB

import global_variables



# Lade die Config global
CONFIG_PATH = os.path.join('intents','functions','usermgmt','config_usermgmt.yml')

USER_JSON_PATH = os.path.join('users.json')
db = TinyDB(USER_JSON_PATH)
speaker_table = db.table('speakers')

def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


@register_call("user_list")
def user_list(session_id="general", dummy=0):
    cfg, language = __read_config__()
    speakers = speaker_table.all()
    if speakers:  # Prüfen, ob die Tabelle Einträge enthält
        user_list = ", ".join([speaker['name'] for speaker in speakers if 'name' in speaker])
        logger.info("user liste: {}", user_list)
        return random.choice(cfg['intent']['user'][language]['available_users']).format(user_list)
    return cfg['intent']['user'][language]['no_users']


@register_call("new_user")
def new_user(session_id="general", dummy=0):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_user_state", None)
    if session_state is None:
        session_state = global_variables.new_user_state = {
            "step": 0,
            "name": None,
            "intents": None,
            "voice_fingerprint": None,
        }

    # Schritte der Benutzererstellung
    if session_state["step"] == 0:
        logger.info("Frage nach Benutzername")
        session_state["step"] += 1
        global_variables.context = handle_new_user_name
        return cfg['intent']['user'][language]['new_user_name']

def handle_new_user_name(user_input=""):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_user_state", None)

    if not session_state:
        return cfg['intent']['user'][language]['no_session']

    if session_state["step"] == 1:
        Speaker = Query()
        existing_user = speaker_table.get(Speaker.name == user_input.strip())

        if existing_user:
            logger.warning(f"Benutzername {user_input} existiert bereits.")
            return random.choice(cfg['intent']['user'][language]['user_exist']).format(user_input)
        session_state["name"] = user_input
        logger.info(f"Benutzername gesetzt: {user_input}")
        session_state["step"] += 1
        global_variables.context = handle_new_user_intents
        return cfg['intent']['user'][language]['new_user_intent']

def handle_new_user_intents(user_input=""):
    if not global_variables.voice_assistant.is_listening:
        global_variables.voice_assistant.is_listening = True
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_user_state", None)

    if not session_state:
        return cfg['intent']['user'][language]['no_session']

    elif session_state["step"] == 2:
        global_variables.voice_assistant.is_listening = False
        if len(user_input.split()) == 1 and user_input.strip().lower() in ["alle", "all"]:
            session_state["intents"] = ["*"]
        else:
            session_state["intents"] = user_input.split(",")
        logger.info(f"Berechtigungen gesetzt: {session_state['intents']}")
        session_state["step"] += 1
        global_variables.context = handle_new_user_voice
        return cfg['intent']['user'][language]['new_user_voice']

def handle_new_user_voice(user_input=""):
    if not global_variables.voice_assistant.is_listening:
        global_variables.voice_assistant.is_listening = True
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_user_state", None)

    if not session_state:
        return cfg['intent']['user'][language]['no_session']

    elif session_state["step"] == 3:
        global_variables.voice_assistant.is_listening = False
        logger.info("Starte Sprachaufnahme...")
        fingerprint = global_variables.voice_assistant.capture_voice_sample()
        if fingerprint is not None and len(fingerprint) > 0:
            session_state["voice_fingerprint"] = fingerprint
            logger.info("Sprachfingerabdruck gespeichert.")
            # Benutzer in die Datenbank einfügen
            speaker_table = global_variables.voice_assistant.user_management.speaker_table
            speaker_table.insert({
                "name": session_state["name"],
                "intents": session_state["intents"],
                "voice": np.array(session_state["voice_fingerprint"]).tolist(),
            })
            logger.info(f"Benutzer {session_state['name']} erfolgreich erstellt.")
            # Sample-User entfernen
            sample_user = speaker_table.get(Query().name == "sample_user")
            if sample_user:
                speaker_table.remove(doc_ids=[sample_user.doc_id])
                logger.info("Sample-User wurde entfernt.")

            # Config aktualisieren
            global_variables.voice_assistant.cfg['assistant']['user_initialized'] = True

            global_variables.new_user_state = None
            global_variables.context = None  # Beende Kontext
            return random.choice(cfg['intent']['user'][language]['add_success']).format(session_state['name'])
        else:
            logger.warning("Sprachaufnahme fehlgeschlagen.")
            return random.choice(cfg['intent']['user'][language]['add_error']).format(session_state['name'])

    return None


#request change intent
@register_call("change_intent_user")
def change_intent_user(session_id="general", user=None):
    cfg, language = __read_config__()
    Speaker = Query()  # TinyDB Query-Objekt
    user = user.strip()

    # Überprüfen, ob der Benutzer existiert
    user_entry = speaker_table.get(Speaker.name == user)
    if not user_entry:
        return random.choice(cfg['intent']['user'][language]['user_noexist']).format(user)

    # Sitzung initialisieren
    session_state = getattr(global_variables, "change_intent_state", None)
    if session_state is None:
        session_state = global_variables.change_intent_state = {
            "step": 0,
            "intents": [],
            "user": user
        }

    if session_state["step"] == 0:
        # Start der Sitzung
        session_state["step"] += 1
        global_variables.context = handle_change_intents
        return f"Berechtigungen für {user} ändern. Bitte sagen Sie die gewünschten Berechtigungen, getrennt durch Leerzeichen, oder 'alle' für uneingeschränkten Zugriff."

def handle_change_intents(user_input=""):
    """
    Verarbeitet die Eingabe des Nutzers, speichert die Intents und beendet die Sitzung.
    """
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "change_intent_state", None)

    if not session_state:
        return cfg['intent']['user'][language]['no_session']

    if len(user_input.split()) == 1 and user_input.strip().lower() in ["alle", "all"]:
        session_state["intents"] = ["*"]
    else:
        session_state["intents"] = user_input.split()

    # Speichere die neuen Intents
    Speaker = Query()
    speaker_table.update({'intents': session_state["intents"]}, Speaker.name == session_state["user"])

    # Sitzung abschließen
    global_variables.change_intent_state = None
    global_variables.context = None

    return random.choice(cfg['intent']['user'][language]['change_intent_success']).format(session_state["user"])


@register_call("delete_user")
def delete_user(session_id="general", user=None):
    cfg, language = __read_config__()
    Speaker = Query()  # TinyDB Query-Objekt
    user = user.strip()

    # Überprüfen, ob der Benutzer existiert
    user_entry = speaker_table.get(Speaker.name == user)
    if user_entry:
        # Benutzer aus der Datenbank löschen
        speaker_table.remove(Speaker.name == user)
        return random.choice(cfg['intent']['user'][language]['delete_success']).format(user)
    return random.choice(cfg['intent']['user'][language]['delete_error']).format(user)


@register_call("change_spkid_user")
def change_spkid_user(session_id="general", user=None):
    cfg, language = __read_config__()
    Speaker = Query()  # TinyDB Query-Objekt
    user = user.strip()

    # Überprüfen, ob der Benutzer existiert
    user_entry = speaker_table.get(Speaker.name == user)
    if not user_entry:
        return random.choice(cfg['intent']['user'][language]['user_noexist']).format(user)

    logger.info(f"Aktualisiere Sprachprofil für {user}.")
    fingerprint = global_variables.voice_assistant.capture_voice_sample()
    if fingerprint is not None and len(fingerprint) > 0:
            # Neuer Sprach-Fingerprint erstellen und speichern
            embedding = global_variables.voice_assistant.encoder.embed_utterance(fingerprint).tolist()
            speaker_table.update({'voice': embedding}, Speaker.name == user)
            return random.choice(cfg['intent']['user'][language]['change_spkid_success']).format(user)

    return random.choice(cfg['intent']['user'][language]['change_error']).format(user)