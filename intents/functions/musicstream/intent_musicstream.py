from loguru import logger
from chatbot import register_call
import constants
import global_variables
import random
import os
import yaml
from fuzzywuzzy import fuzz
from words2num import w2n
from marianMTModels import Translator


@register_call("musicstream")
def musicstream(session_id="general", station=None):
    config_path = constants.find_data_file(os.path.join('intents', 'functions', 'musicstream', 'config_musicstream.yml'))
    cfg = None

    with open(config_path, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

    if not cfg:
        logger.error("Konnte Konfigurationsdatei für das Musikstreaming nicht lesen.")
        return ""

    # Holen der Sprache aus der globalen Konfigurationsdatei
    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    # Meldung falls der Sender nicht gefunden wurde
    UNKNOWN_STATION = random.choice(cfg['intent']['musicstream'][LANGUAGE]['unknown_station'])

    # Radiosender haben häufig Zahlen in den Namen, weswegen wir für einen besseren Abgleich
    # Zahlenwörter in Zahlenwerte umwandeln.
    marian = Translator(LANGUAGE, 'en')
    station = marian.translate([station.strip()])[0].lower()

    word_str = station.split(" ")
    words2num_res = ""
    for i in word_str:
        try:
            words2num_res += str(w2n(i)) + " "
        except:
            words2num_res += i + " "
    station = words2num_res
    logger.info("words2num: {}", station)

    # Wir eliminieren weiterhin alle Whitespaces, denn das Buchstabieren in VOSK bringt
    # pro Buchstabe eine Leerstelle mit sich.
    station = "".join(station.split())

    station_stream = None
    for key, value in cfg['intent']['musicstream']['stations'].items():

        # Wir führen eine Fuzzy-Suche aus, da die Namen der Radiosender nicht immer perfekt
        # von VOSK erkannt werden.
        ratio = fuzz.ratio(station.lower(), key.lower())
        logger.info("Übereinstimmung von {} und {} ist {}%", station, key, ratio)
        if ratio > 60:
            station_stream = value
            logger.info("Station '{}' erkannt mit URL '{}'.".format(key, station_stream))
            break

    # Wurde kein Sender gefunden?
    if station_stream is None:
        logger.debug("Kein Sender mit dem Namen '{}' gefunden.".format(station))
        return UNKNOWN_STATION
    else:
        logger.debug("Starte Streaming von '{}' mit URL '{}'.".format(station, station_stream))

    global_variables.voice_assistant.audio_player.play_stream(station_stream)

    # Der Assistent muss nicht sprechen, wenn ein Radiostream gespielt wird
    return ""
