import os
import random
import yaml
from chatbot import register_call
from loguru import logger
import global_variables
from global_variables import voice_assistant
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Lade die Config global
CONFIG_PATH = os.path.join('intents','functions','language','config_language.yml')
# Pfad zur Sprachdatei
LANGUAGES_PATH = os.path.join('languages.yml')
# Pfad zur Main-Konfigurationsdatei
MAIN_CONFIG_PATH = os.path.join('config.yml')


def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


def __load_languages__():
    if os.path.exists(LANGUAGES_PATH):
        with open(LANGUAGES_PATH, "r", encoding="utf-8") as ymlfile:
            languages_cfg = yaml.safe_load(ymlfile)
            return languages_cfg.get("languages", {})
    return {}


@register_call("language_list")
def language_list(session_id="general", dummy=0):
    languages_cfg = __load_languages__()
    cfg, language = __read_config__()
    logger.info(f"language: {languages_cfg}")

    # Mapping von Sprachkürzeln zu Ländernamen
    language_names = {
        'de': 'Deutsch',
        'en': 'Englisch',
        'es': 'Spanisch',
        'fr': 'Französisch',
        'it': 'Italienisch',
        'ja': 'Japanisch',
        'ru': 'Russisch'
    }

    available_languages = ", ".join([language_names.get(lang, lang) for lang in languages_cfg.keys()])
    logger.info(f"Available languages: {available_languages}")
    AVIALABLE_LANGUAGES = random.choice(cfg['intent']['language'][language]['available_languages'])
    AVIALABLE_LANGUAGES = AVIALABLE_LANGUAGES.format(available_languages)
    return AVIALABLE_LANGUAGES


@register_call("switch_language")
def switch_language(session_id="general", language=None):
    languages_cfg = __load_languages__()
    cfg, current_language = __read_config__()

    language = language.strip().lower()

    # Mögliche Sprachzuordnungen (für Übersetzung, wenn Nutzer "Deutsch" statt "de" sagt)
    language_map = {
        "deutsch": "de",
        "englisch": "en",
        "französisch": "fr",
        "spanisch": "es",
        "italienisch": "it",
        "japanisch": "ja",
        "russisch": "ru"
    }

    # Abgleich der gewünschten Sprache mit dem `language_map`
    language_code = language_map.get(language)
    logger.info(f"language code: {language_code}")
    if not language_code or language_code not in languages_cfg:
        ERROR_LANGUAGE = random.choice(cfg['intent']['language'][current_language]['error_language'])
        ERROR_LANGUAGE = ERROR_LANGUAGE.format(language)
        return ERROR_LANGUAGE

    logger.info(f"Switch language: {global_variables.voice_assistant.available_voices}")
    # Wechsel zur neuen Sprache im Sprachassistenten
    if language_code in global_variables.voice_assistant.available_voices:
        chosen_voice = random.choice(global_variables.voice_assistant.available_voices[language_code])
        global_variables.voice_assistant.tts.set_voice(chosen_voice)

        global_variables.voice_assistant.cfg['assistant']['language'] = language_code

        logger.info(f"Sprache gewechselt zu {language_code} mit Stimme {chosen_voice}")
        CHANGE_SUCCESS = random.choice(cfg['intent']['language'][language_code]['change_success'])
        CHANGE_SUCCESS = CHANGE_SUCCESS.format(language)
        response = CHANGE_SUCCESS
    else:
        ERROR_LANGUAGE = random.choice(cfg['intent']['language'][language_code]['error_language'])
        ERROR_LANGUAGE = ERROR_LANGUAGE.format(language)
        return ERROR_LANGUAGE

    return response