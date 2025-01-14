from loguru import logger
from chatbot import register_call
from words2num import w2n
import constants
import global_variables
import yaml
import random
import os
from marianMTModels import Translator

MAIN_CONFIG_PATH = constants.find_data_file(os.path.join('config.yml'))


def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    config_path = constants.find_data_file(os.path.join('intents','functions','volume','config_volume.yml'))
    with open(config_path, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


@register_call("getVolume")
def getVolume(session_id = "general", dummy=0):
    cfg, language = __read_config__()
    logger.info("Lautstärke ist {} von zehn.", int(global_variables.voice_assistant.volume * 10))
    return cfg['intent']['volume'][language]['volume_is'].format(int(global_variables.voice_assistant.volume * 10))


@register_call("maxVolume")
def getVolume(session_id = "general", dummy=0):
    cfg, language = __read_config__()
    max_volume = round(10.0 / 10.0, 1)
    global_variables.voice_assistant.tts.set_volume(max_volume)
    global_variables.voice_assistant.audio_player.set_volume(max_volume)
    global_variables.voice_assistant.volume = max_volume
    logger.info("Lautstärke ist {} von zehn.", int(global_variables.voice_assistant.volume * 10))
    return cfg['intent']['volume'][language]['set_volume'].format(int(global_variables.voice_assistant.volume * 10))


@register_call("setVolume")
def setVolume(session_id = "general", volume=None):
    cfg, language = __read_config__()
    volume = volume.strip()
    if volume == "":
        return getVolume(session_id, 0)
    volume = "neun" if volume == "neuen" else "acht" if volume == "achten" else volume
    translator = Translator(language, "en")
    volume = translator.translate(volume)[0].lower()
    # konvertiere das Zahlenwort in einen geladenanzzahligen Wert
    if isinstance(volume, str):
        try:
            volume = str(w2n(volume))
        except:
            return random.choice(cfg['intent']['volume'][language]['invalid_volume'])
    num_vol = int(volume)

    # Konnte die Konfigurationsdatei des Intents geladen werden?
    if cfg:

        if num_vol < 0 or num_vol > 10:
            logger.info("Lautstärke {} ist ungültig, nur Werte von 0 - 10 sind erlaubt.", num_vol)
            return random.choice(cfg['intent']['volume'][language]['invalid_volume'])
        else:
            new_volume = round(num_vol / 10.0, 1)
            logger.info("Setze Lautstärke von {} auf {}.", global_variables.voice_assistant.volume, new_volume)
            global_variables.voice_assistant.tts.set_volume(new_volume)
            # mixer.music.set_volume(new_volume)
            global_variables.voice_assistant.audio_player.set_volume(new_volume)
            global_variables.voice_assistant.volume = new_volume
            return cfg['intent']['volume'][language]['set_volume'].format(int(global_variables.voice_assistant.volume * 10))
    else:
        logger.error("Konnte Konfigurationsdatei für Intent 'volume' nicht laden.")
        return ""


@register_call("volumeUp")
def volumeUp(session_id = "general", volume=None):
    cfg, language = __read_config__()

    # konvertiere das Zahlenwort in einen geladenanzzahligen Wert
    vol_up = 1
    if cfg:

        if isinstance(volume, str):
            vol_up = volume.split().count(cfg['intent']['volume'][language]['volume_up']) # Erlaube etwas wie "lauter, lauter, lauter"

        vol = global_variables.voice_assistant.volume

        new_volume = round(min(1.0, (vol + vol_up / 10.0)), 1)
        logger.info("Setze Lautstärke von {} auf {}.", global_variables.voice_assistant.volume, new_volume)
        logger.debug("Setze Lautstärke auf {}.", new_volume)
        global_variables.voice_assistant.tts.set_volume(new_volume)
        global_variables.voice_assistant.audio_player.set_volume(new_volume)
        global_variables.voice_assistant.volume = new_volume
        return ""
    else:
        logger.error("Konnte Konfigurationsdatei für Intent 'volume' nicht laden.")
        return ""


@register_call("volumeDown")
def volumeDown(session_id = "general", volume=None):
    cfg, language = __read_config__()

    vol_down = 1
    if cfg:

        if isinstance(volume, str):
            vol_down = volume.split().count(cfg['intent']['volume'][language]['volume_down']) # Erlaube etwas wie "lauter, lauter, lauter"

        vol = global_variables.voice_assistant.volume

        new_volume = round(max(0.0, (vol - vol_down / 10.0)), 1)
        logger.info("Setze Lautstärke von {} auf {}.", global_variables.voice_assistant.volume, new_volume)
        logger.debug("Setze Lautstärke auf {}.", new_volume)
        global_variables.voice_assistant.tts.set_volume(new_volume)
        global_variables.voice_assistant.audio_player.set_volume(new_volume)
        global_variables.voice_assistant.volume = new_volume
        return ""
    else:
        logger.error("Konnte Konfigurationsdatei für Intent 'volume' nicht laden.")
        return ""