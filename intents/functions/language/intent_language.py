import os
import random
import yaml
from chatbot import register_call
from loguru import logger
from vosk import Model, SpkModel, KaldiRecognizer
import constants
import global_variables
from global_variables import voice_assistant
from vosk_model_downloader import download_vosk_model


BASE_DIR = constants.find_data_file(os.path.dirname(os.path.abspath(__file__)))
# Lade die Config global
CONFIG_PATH = constants.find_data_file(os.path.join('intents', 'functions', 'language', 'config_language.yml'))
# Pfad zur Sprachdatei
LANGUAGES_PATH = constants.find_data_file(os.path.join('languages.yml'))
# Pfad zur Main-Konfigurationsdatei
MAIN_CONFIG_PATH = constants.find_data_file(os.path.join('config.yml'))


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
    languages_map = {
        "de": {"de": "Deutsch", "en": "German", "fr": "Allemand", "es": "Alemán", "it": "Tedesco", "ja": "ドイツ語", "ru": "Немецкий"},
        "en": {"de": "Englisch", "en": "English", "fr": "Anglais", "es": "Inglés", "it": "Inglese", "ja": "英語", "ru": "Английский"},
        "fr": {"de": "Französisch", "en": "French", "fr": "Français", "es": "Francés", "it": "Francese", "ja": "フランス語", "ru": "Французский"},
        "es": {"de": "Spanisch", "en": "Spanish", "fr": "Espagnol", "es": "Español", "it": "Spagnolo", "ja": "スペイン語", "ru": "Испанский"},
        "it": {"de": "Italienisch", "en": "Italian", "fr": "Italien", "es": "Italiano", "it": "Italiano", "ja": "イタリア語", "ru": "Итальянский"},
        "ja": {"de": "Japanisch", "en": "Japanese", "fr": "Japonais", "es": "Japonés", "it": "Giapponese", "ja": "日本語", "ru": "Японский"},
        "ru": {"de": "Russisch", "en": "Russian", "fr": "Russe", "es": "Ruso", "it": "Russo", "ja": "ロシア語", "ru": "Русский"}
    }

    available_languages = []
    for lang_code, translations in languages_map.items():
        translated_name = translations.get(language, lang_code)
        available_languages.append(translated_name)
    available_languages_str = ", ".join(available_languages)
    logger.info(f"Available languages: {available_languages_str}")
    AVIALABLE_LANGUAGES = random.choice(cfg['intent']['language'][language]['available_languages'])
    AVIALABLE_LANGUAGES = AVIALABLE_LANGUAGES.format(available_languages_str)
    return AVIALABLE_LANGUAGES


@register_call("switch_language")
def switch_language(session_id="general", language=None):
    languages_cfg = __load_languages__()
    cfg, current_language = __read_config__()

    language = language.strip().lower()

    # Mögliche Sprachzuordnungen (für Übersetzung, wenn Nutzer "Deutsch" statt "de" sagt)
    language_map = {
        "de": ["deutsch", "german", "allemand", "alemán", "tedesco", "ドイツ語", "немецкий"],
        "en": ["englisch", "english", "anglais", "inglés", "inglese", "英語", "английский"],
        "fr": ["französisch", "french", "français", "francés", "francese", "フランス語", "французский"],
        "es": ["spanisch", "spanish", "espagnol", "español", "spagnolo", "スペイン語", "испанский"],
        "it": ["italienisch", "italian", "italien", "italiano", "italiano", "イタリア語", "итальянский"],
        "ja": ["japanisch", "japanese", "japonais", "japonés", "giapponese", "日本語", "японский"],
        "ru": ["russisch", "russian", "russe", "ruso", "russo", "ロシア語", "русский"],
    }

    # Abgleich der gewünschten Sprache mit dem `language_map`
    language_code = None
    for code, aliases in language_map.items():
        if language in aliases:
            language_code = code
            logger.info(f"language code: {language_code}")
    if not language_code or language_code not in languages_cfg:
        ERROR_LANGUAGE = random.choice(cfg['intent']['language'][current_language]['error_language'])
        ERROR_LANGUAGE = ERROR_LANGUAGE.format(language)
        return ERROR_LANGUAGE

    logger.info(f"Switch language: {global_variables.voice_assistant.available_voices}")
    global_variables.voice_assistant.say_with_language(global_variables.voice_assistant.tts, global_variables.voice_assistant.lang_manager, "intent.tts.lang_switch_start")
    if language_code in global_variables.voice_assistant.available_voices:

        # Sprachmodell neu laden
        try:
            speaker_model_path = download_vosk_model("spk", global_variables.voice_assistant.download)
            s2t_model_path = download_vosk_model(language_code, global_variables.voice_assistant.download)

            s2t_model = Model(s2t_model_path)
            speaker_model = SpkModel(speaker_model_path)

            # Aktualisiere Kaldi-Erkenner
            global_variables.voice_assistant.rec = KaldiRecognizer(s2t_model, 16000, speaker_model)
            chosen_voice = random.choice(global_variables.voice_assistant.available_voices[language_code])
            global_variables.voice_assistant.tts.set_voice(chosen_voice)

            global_variables.voice_assistant.cfg['assistant']['language'] = language_code

            global_variables.voice_assistant.intent_management.language_manager.set_language(language_code)

            # TTS: Neue Sprache initialisiert
            logger.info(f"Sprache gewechselt zu {language_code} mit Stimme {chosen_voice}")
            global_variables.voice_assistant.say_with_language(global_variables.voice_assistant.tts, global_variables.voice_assistant.lang_manager, "intent.tts.lang_switch_end")

            # Antwort an den Benutzer
            CHANGE_SUCCESS = random.choice(cfg['intent']['language'][language_code]['change_success'])
            CHANGE_SUCCESS = CHANGE_SUCCESS.format(language)
            response = CHANGE_SUCCESS

        except Exception as e:
            logger.error(f"Fehler beim Wechsel des Sprachmodells: {e}")
            ERROR_MODEL = random.choice(cfg['intent']['language'][current_language]['error_model'])
            ERROR_MODEL = ERROR_MODEL.format(language)
            return ERROR_MODEL

    else:
        ERROR_LANGUAGE = random.choice(cfg['intent']['language'][language_code]['error_language'])
        ERROR_LANGUAGE = ERROR_LANGUAGE.format(language)
        return ERROR_LANGUAGE

    return response
