from loguru import logger
from chatbot import register_call
import global_variables
import random
import os
import yaml
from fuzzywuzzy import fuzz
from transformers import MarianMTModel, MarianTokenizer
from typing import Sequence
from words2num import w2n

class Translator:
    def __init__(self, source_lang: str, dest_lang: str, model_dir="./MarianMTModel") -> None:
        if source_lang == dest_lang:
            self.is_identity_translation = True
            return

        self.is_identity_translation = False

        self.model_name = f"opus-mt-{source_lang}-{dest_lang}"
        self.model_path = os.path.join(model_dir, self.model_name)

        # Lade das Modell und den Tokenizer aus dem lokalen Verzeichnis
        self.model = MarianMTModel.from_pretrained(self.model_path, local_files_only=True)
        self.tokenizer = MarianTokenizer.from_pretrained(self.model_path, local_files_only=True)

    def translate(self, texts: Sequence[str]) -> Sequence[str]:
        if self.is_identity_translation:
            return texts

        tokens = self.tokenizer(list(texts), return_tensors="pt", padding=True)
        translate_tokens = self.model.generate(**tokens)
        return [self.tokenizer.decode(t, skip_special_tokens=True) for t in translate_tokens]

@register_call("musicstream")
def musicstream(session_id="general", station=None):
    config_path = os.path.join('intents','functions','musicstream','config_musicstream.yml')
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