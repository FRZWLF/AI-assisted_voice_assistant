import hashlib
from loguru import logger
from chatbot import register_call
import constants
import global_variables
import yaml
import random
import os
from pykeepass import PyKeePass, create_database
from pynput.keyboard import Key, Listener, Controller as keyboard_controller
from fuzzywuzzy import fuzz
import json
import numpy as np
from resemblyzer import VoiceEncoder
from resemblyzer.audio import preprocess_wav

from marianMTModels import Translator

CONFIG_PATH = constants.find_data_file(os.path.join('intents','functions','password','config_password.yml'))

def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


def verify_speaker(input_fingerprint, saved_fingerprint, threshold=0.2):
    """
    Überprüft die Ähnlichkeit zwischen einem aktuellen und einem gespeicherten Fingerprint.

    :param input_fingerprint: Der aktuelle Fingerprint als numpy-Array.
    :param saved_fingerprint: Der gespeicherte Fingerprint als numpy-Array.
    :param threshold: Schwellenwert für die minimale Ähnlichkeit.
    :return: True, wenn der Sprecher erfolgreich verifiziert wurde, False sonst.
    """
    encoder = VoiceEncoder()
    try:
        # Verarbeite den Input
        if not isinstance(input_fingerprint, np.ndarray):
            input_fingerprint = np.array(input_fingerprint, dtype=np.float32)

        processed_wav = preprocess_wav(input_fingerprint)
        input_fingerprint = encoder.embed_utterance(processed_wav)
    except Exception as e:
        logger.error(f"Fehler beim Verarbeiten der Sprachaufnahme: {e}")
        return "Unbekannt"

    if not isinstance(saved_fingerprint, np.ndarray):
        try:
            saved_fingerprint = np.array(saved_fingerprint, dtype=np.float32)
        except Exception as e:
            logger.error(f"Konvertierung des Saved-Fingerprints fehlgeschlagen: {e}")
            return False

    # Überprüfung der Länge
    if len(input_fingerprint) != len(saved_fingerprint):
        logger.error(f"Dimension mismatch: Input ({len(input_fingerprint)}) != Saved ({len(saved_fingerprint)})")
        return False

    # Überprüfung der Norm (keine Null-Vektoren)
    if np.linalg.norm(input_fingerprint) == 0 or np.linalg.norm(saved_fingerprint) == 0:
        logger.error("Einer der Fingerprints hat eine Norm von 0. Daten ungültig.")
        return False

    # Fingerprints normalisieren
    input_fingerprint_normalized = input_fingerprint / np.linalg.norm(input_fingerprint)
    saved_fingerprint_normalized = saved_fingerprint / np.linalg.norm(saved_fingerprint)

    # Cosinus-Ähnlichkeit berechnen
    try:
        cosine_similarity = np.dot(input_fingerprint_normalized, saved_fingerprint_normalized)
        logger.info(f"Berechnete Cosinus-Ähnlichkeit: {cosine_similarity:.3f}")
    except Exception as e:
        logger.error(f"Fehler bei der Berechnung der Cosinus-Ähnlichkeit: {e}")
        return False

    # Schwellenwertprüfung
    if cosine_similarity < threshold:
        logger.warning(f"Ähnlichkeit ({cosine_similarity:.3f}) unterhalb des Schwellenwerts ({threshold}).")
        return False

    logger.info("Sprecher erfolgreich verifiziert.")
    return True


@register_call("getPassword")
def getPassword(session_id = "general", entry="none"):
    cfg, LANGUAGE = __read_config__()

    username = global_variables.voice_assistant.current_speaker
    key_file = constants.find_data_file(os.path.join("user_databases", username, "key.keyx"))
    db_file = constants.find_data_file(os.path.join("user_databases", username, f"{username}.kdbx"))
    typed_pw = cfg['intent']['password'][LANGUAGE]['typed_pw']

    if not os.path.exists(db_file):
        return cfg['intent']['password'][LANGUAGE]['db_not_found']

    if not os.path.exists(key_file):
        return cfg['intent']['password'][LANGUAGE]['key_not_found']

    UNKNOWN_ENTRY = random.choice(cfg['intent']['password'][LANGUAGE]['unknown_entry'])
    UNKNOWN_ENTRY = UNKNOWN_ENTRY.format(entry)

    NO_VOICE_MATCH = cfg['intent']['password'][LANGUAGE]['no_voice_match']

    try:
        kp = PyKeePass(os.path.abspath(db_file), keyfile=os.path.abspath(key_file))
    except Exception as e:
        return cfg['intent']['password'][LANGUAGE]['could_not_access_keystore']
    # Verifiziere Stimme
    fp_entry = kp.find_entries(title='_fingerprint', first=True)
    if fp_entry:
        saved_fingerprint = json.loads(fp_entry.notes)
        current_fingerprint = global_variables.voice_assistant.current_speaker_fingerprint

        # Stimme überprüfen
        if not verify_speaker(current_fingerprint, saved_fingerprint, threshold=0.2):
            return NO_VOICE_MATCH
    else:
        logger.warning("Kein '_fingerprint'-Eintrag gefunden.")

    entries = kp.entries
    for title in entries:
        ratio = fuzz.ratio(title.title.lower(), entry.lower())
        logger.info("Übereinstimmung von {} und {} ist {}%", title.title, entry, ratio)
        if ratio > 70:
            if (title):
                keyboard = keyboard_controller()
                keyboard.type(title.password)
                return typed_pw.format(title.title)
    return UNKNOWN_ENTRY


@register_call("getUsername")
def getUsername(session_id = "general", entry="none"):
    cfg, LANGUAGE = __read_config__()

    username = global_variables.voice_assistant.current_speaker
    key_file = constants.find_data_file(os.path.join("user_databases", username, "key.keyx"))
    db_file = constants.find_data_file(os.path.join("user_databases", username, f"{username}.kdbx"))

    if not os.path.exists(db_file):
        return cfg['intent']['password'][LANGUAGE]['db_not_found']

    if not os.path.exists(key_file):
        return cfg['intent']['password'][LANGUAGE]['key_not_found']

    UNKNOWN_ENTRY = random.choice(cfg['intent']['password'][LANGUAGE]['unknown_entry']).format(entry)

    NO_VOICE_MATCH = cfg['intent']['password'][LANGUAGE]['no_voice_match']

    try:
        kp = PyKeePass(os.path.abspath(db_file), keyfile=os.path.abspath(key_file))
    except Exception as e:
        return cfg['intent']['password'][LANGUAGE]['could_not_access_keystore']

    # Verifiziere Stimme
    fp_entry = kp.find_entries(title='_fingerprint', first=True)
    if fp_entry:
        saved_fingerprint = json.loads(fp_entry.notes)
        current_fingerprint = global_variables.voice_assistant.current_speaker_fingerprint

        # Stimme überprüfen
        if not verify_speaker(current_fingerprint, saved_fingerprint, threshold=0.2):
            return NO_VOICE_MATCH
    else:
        logger.warning("Kein '_fingerprint'-Eintrag gefunden.")

    entries = kp.entries
    logger.info(entries)
    logger.debug(f"Verfügbare Titel in KeePass: {[entry.title for entry in entries]}")
    for title in entries:
        ratio = fuzz.ratio(title.title.lower(), entry.lower())
        logger.info("Übereinstimmung von {} und {} ist {}%", title.title, entry, ratio)
        if ratio > 70:

            if (title):
                return title.username

    return UNKNOWN_ENTRY


def create_user_db(username, keyfile_path, fingerprint):
    """
    Erstellt eine KeePass-Datenbank für einen Benutzer und speichert den Voice-Fingerprint.

    :param username: Name des Benutzers (wird für den Datenbankpfad verwendet).
    :param keyfile_path: Pfad zur Schlüsseldatei.
    :param fingerprint: Voice-Fingerprint des Benutzers.
    """
    db_dir = constants.find_data_file(os.path.join('user_databases', username))
    os.makedirs(db_dir, exist_ok=True)  # Erstelle Benutzerverzeichnis
    db_path = constants.find_data_file(os.path.join(db_dir, f"{username}.kdbx"))
    keyfile_path = constants.find_data_file(keyfile_path)

    generate_key_file(keyfile_path)

    # KeePass-Datenbank erstellen
    create_database(db_path, password=None, keyfile=keyfile_path)
    kp = PyKeePass(db_path, password=None, keyfile=keyfile_path)

    # Fingerprint validieren
    if not isinstance(fingerprint, np.ndarray):
        raise ValueError("Fingerprint muss ein numpy.ndarray sein.")

    if np.linalg.norm(fingerprint) == 0:
        raise ValueError("Ungültiger Fingerprint: Norm ist 0.")

    # Fingerprint überprüfen und nur normalisieren, wenn nötig
    if not np.isclose(np.linalg.norm(fingerprint), 1.0, atol=1e-6):
        fingerprint = fingerprint / np.linalg.norm(fingerprint)

    fingerprint_list = fingerprint.tolist()

    # Fingerprint speichern
    kp.add_entry(kp.root_group, '_fingerprint', '', '', notes=json.dumps(fingerprint_list))
    kp.save()

    return db_path


def generate_key_file(keyfile_path):
    """
    Generiert eine KeePass-kompatible Schlüsseldatei.

    :param keyfile_path: Pfad zur Schlüsseldatei.
    """
    # Konvertiere den Schlüssel in das KeePass-XML-Format
    random_key = os.urandom(32)  # 32 zufällige Bytes
    key_data = random_key.hex().upper()

    # Teile die Hex-Daten in 8-Zeichen-Blöcke auf
    key_chunks = " ".join([key_data[i:i+8] for i in range(0, len(key_data), 8)])

    # Erzeuge den Hash des Schlüssels (nur zur Validierung, wie KeePass es macht)
    key_hash = hashlib.sha256(random_key).hexdigest().upper()[:8]


    keyfile_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<KeyFile>
    <Meta>
        <Version>2.0</Version>
    </Meta>
    <Key>
        <Data Hash="{key_hash}">
            {key_chunks}
        </Data>
    </Key>
</KeyFile>
"""

    # Schreibe die Datei
    with open(keyfile_path, "w", encoding="utf-8") as keyfile:
        keyfile.write(keyfile_content)
    return keyfile_path


@register_call("newEntity")
def newEntity(session_id:"general", dummy=0):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_db_entity_state", None)
    if session_state is None:
        session_state = global_variables.new_db_entity_state = {
            "step": 0,
            "titel": None,
            "username": None,
            "password": None,
        }

    # Schritte der Benutzererstellung
    if session_state["step"] == 0:
        logger.info("Frage nach Benutzername")
        session_state["step"] += 1
        global_variables.context = handle_new_entity_title
        return cfg['intent']['password'][language]['new_entity_title']


def handle_new_entity_title(user_input=""):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_db_entity_state", None)

    if not session_state:
        return cfg['intent']['password'][language]['no_session']

    if session_state["step"] == 1:
        session_state["title"] = user_input.strip()
        logger.info(f"Titel des neuen Eintrags gesetzt: {session_state['title']}")
        session_state["checkup_step"] = "title_check"
        global_variables.context = check_up
        return cfg['intent']['password'][language]['check_up_title'].format(session_state['title'])

def handle_new_entity_username(user_input=""):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_db_entity_state", None)

    if not session_state:
        return cfg['intent']['password'][language]['no_session']

    if session_state["step"] == 2:
        # Lade und parse die Mapping-Tabelle für Usernamen/E-Mails
        username_email_map = cfg['intent']['password'][language]['char_map']
        username_email_map = dict(item.split("=") for item in username_email_map.split(","))

        # Konvertiere den User-Input
        user_input = user_input.lower()
        parts = user_input.split()
        converted_parts = [username_email_map.get(word, word) for word in parts]
        username = "".join(converted_parts)

        session_state["username"] = username.strip()
        logger.info(f"Benutzername für den neuen Eintrag gesetzt: {session_state['username']}")
        session_state["checkup_step"] = "username_check"
        global_variables.context = check_up
        return cfg['intent']['password'][language]['check_up_username'].format(session_state['username'])

def handle_new_entity_pw(user_input=""):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_db_entity_state", None)

    if not session_state:
        return cfg['intent']['password'][language]['no_session']

    if session_state["step"] == 3:
        # Mapping für buchstabierte Zeichen und Sonderzeichen
        char_map = cfg['intent']['password'][language]['char_map']
        char_map = dict(item.split("=") for item in char_map.split(","))

        user_input = user_input.lower()
        parts = user_input.split()
        converted_parts = [char_map.get(word, word) for word in parts]
        password = "".join(converted_parts)

        session_state["password"] = password.strip()
        logger.info(f"Passwort für den neuen Eintrag gesetzt: {session_state['password']}")
        session_state["checkup_step"] = "password_check"
        global_variables.context = check_up
        return cfg['intent']['password'][language]['check_up_pw'].format(session_state['password'])

def finish_new_entity(user_input=""):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_db_entity_state", None)

    if not session_state:
        return cfg['intent']['password'][language]['no_session']

    if session_state["step"] == 4:
        speaker = global_variables.voice_assistant.current_speaker

        if not speaker:
            logger.error("Kein Sprecher erkannt.")
            return cfg['intent']['password'][language]['no_speaker']

        # Datenbank und Schlüsseldatei abrufen
        username = speaker  # Der erkannte Benutzername
        keyfile_path = constants.find_data_file(os.path.join("user_databases", username, "key.keyx"))
        db_path = constants.find_data_file(os.path.join("user_databases", username, f"{username}.kdbx"))

        if not os.path.exists(db_path) or not os.path.exists(keyfile_path):
            logger.error(f"Datenbank oder Schlüsseldatei für Benutzer {username} nicht gefunden.")
            return random.choice(cfg['intent']['password'][language]['db_user_not_found']).format(username)

        try:
            # Öffne die Benutzer-Datenbank und füge den neuen Eintrag hinzu
            kp = PyKeePass(db_path, password=None, keyfile=keyfile_path)
            kp.add_entry(
                kp.root_group,
                session_state["title"],
                session_state["username"],
                session_state["password"],
            )
            kp.save()

            logger.info(f"Neuer Eintrag '{session_state['title']}' erfolgreich für {username} erstellt.")
            global_variables.new_db_entity_state = None
            global_variables.context = None
            return random.choice(cfg['intent']['password'][language]['new_entity_success']).format(session_state['title'])

        except Exception as e:
            logger.error(f"Fehler beim Speichern des neuen Eintrags: {e}")
            return cfg['intent']['password'][language]['new_entity_error']

    return None

def check_up(user_input=""):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_db_entity_state", None)

    words = user_input.split()
    user_input = words[0] if words else None

    if session_state["checkup_step"] == "title_check":
        if user_input.lower() in ["ja", "yes"]:
            session_state["checkup_step"] = None
            session_state["step"] += 1
            global_variables.context = handle_new_entity_username
            return cfg['intent']['password'][language]['new_entity_username']
        elif user_input.lower() in ["nein", "no"]:
            session_state["checkup_step"] = None
            global_variables.context = handle_new_entity_title
            return cfg['intent']['password'][language]['retry_title']

    # Checkup für den Username
    elif session_state["checkup_step"] == "username_check":
        if user_input.lower() in ["ja", "yes"]:
            session_state["checkup_step"] = None
            session_state["step"] += 1
            global_variables.context = handle_new_entity_pw
            return cfg['intent']['password'][language]['new_entity_pw']
        elif user_input.lower() in ["nein", "no"]:
            session_state["checkup_step"] = None
            global_variables.context = handle_new_entity_username
            return cfg['intent']['password'][language]['retry_username']

    # Checkup für das Passwort
    elif session_state["checkup_step"] == "password_check":
        if user_input.lower() in ["ja", "yes"]:
            session_state["checkup_step"] = None
            session_state["step"] += 1
            global_variables.context = finish_new_entity
            return finish_new_entity()
        elif user_input.lower() in ["nein", "no"]:
            session_state["checkup_step"] = None
            global_variables.context = handle_new_entity_pw
            return cfg['intent']['password'][language]['retry_pw']

    return cfg['intent']['password'][language]['invalid_response']