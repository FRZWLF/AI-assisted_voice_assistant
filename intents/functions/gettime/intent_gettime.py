from datetime import datetime
import pytz
from chatbot import register_call

import global_variables
import os
import random
import yaml
from loguru import logger


def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    config_path = os.path.join('intents','functions','gettime','config_gettime.yml')
    with open(config_path, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE

@register_call("gettime")
def gettime(session_id="general",dummy=0):
    cfg, language = __read_config__()

    now = datetime.now()
    TIME_HERE = random.choice(cfg['intent']['gettime'][language]['time_here'])
    TIME_HERE = TIME_HERE.format(str(now.hour), str(now.minute))
    return TIME_HERE

@register_call("gettimeplace")
def gettimeplace(session_id="general",place="default"):
    cfg, language = __read_config__()

    # Der Ort ist nicht bekannt
    PLACE_UNKNOWN = random.choice(cfg['intent']['gettime'][language]['place_not_found'])

    # Wir fügen den unbekannten Ort in die Antwort ein
    PLACE_UNKNOWN = PLACE_UNKNOWN.format(place)

    # Lesen aller Orte aus der Konfigurationsdatei
    country_timezone_map = {}
    for key, value in cfg['intent']['gettime']['timezones'].items():
        country_timezone_map[key] = value

    # Versuche den angefragten Ort einer Zeitzone zuzuordnen
    timezone = None
    for c in country_timezone_map:
        if place.strip().lower() in country_timezone_map[c]:
            timezone = pytz.timezone(c)
            break

    # Wurde eine Zeitzone gefunden?
    if timezone:
        now = datetime.now(timezone)
        TIME_AT_PLACE = random.choice(cfg['intent']['gettime'][language]['time_in_place'])
        TIME_AT_PLACE = TIME_AT_PLACE.format(str(now.hour), str(now.minute), place.capitalize())
        return TIME_AT_PLACE

    # Wurde ein Ort angefragt, der nicht gefunden wurde, dann antworte entsprechend
    return PLACE_UNKNOWN