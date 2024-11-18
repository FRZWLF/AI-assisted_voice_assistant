import os
import json
import random
import yaml
from resemblyzer import VoiceEncoder
from chatbot import register_call
from loguru import logger
import global_variables

encoder = VoiceEncoder()

# Lade die Config global
CONFIG_PATH = os.path.join('intents','functions','usermanagement','config_usermgmt.yml')

USER_JSON_PATH = os.path.join('users.json')


def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE

def load_users():
    if os.path.exists(USER_JSON_PATH):
        with open(USER_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"speakers": {}}

def save_users(data):
    with open(USER_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


@register_call("user_list")
def user_list(session_id="general", dummy=0):
    cfg, language = __read_config__()
    users = load_users()
    if users["speakers"]:
        user_list = ", ".join(users["speakers"].keys())
        AVIALABLE_USERS = random.choice(cfg['intent']['user'][language]['available_users'])
        AVIALABLE_USERS = AVIALABLE_USERS.format(user_list)
        return AVIALABLE_USERS
    return cfg['intent']['user'][language]['no_users']


@register_call("new_user")
def new_user(session_id="general", user=None):
    cfg, language = __read_config__()
    users = load_users()
    if user in users["speakers"]:
        return cfg['intent']['user'][language]['user_exist'].format(user)

    # Sprachfingerabdruck aufnehmen
    logger.info(f"Nehme Sprachfingerabdruck für {user} auf.")
    voice_sample = global_variables.voice_assistant.capture_voice_sample()
    if voice_sample:
        embedding = encoder.embed_utterance(voice_sample).tolist()
        users["speakers"][user] = {"voice": embedding, "intents": ["*"]}
        save_users(users)
        return cfg['intent']['user'][language]['add_success'].format(user)
    return cfg['intent']['user'][language]['add_error'].format(user)

#request change intent
@register_call("change_intent_user")
def change_intent_user(session_id="general", user=None):
    cfg, language = __read_config__()
    users = load_users()
    if user not in users["speakers"]:
        return cfg['intent']['user'][language]['user_noexist'].format(user)

    # Berechtigungen ändern (Beispiel)
    intents = input(f"Berechtigungen für {user} (getrennt durch Komma, '*' für alle): ").split(',')
    users["speakers"][user]["intents"] = [i.strip() for i in intents]
    save_users(users)
    return cfg['intent']['user'][language]['change_intent_success'].format(user)

@register_call("delete_user")
def delete_user(session_id="general", user=None):
    cfg, language = __read_config__()
    users = load_users()
    if user in users["speakers"]:
        del users["speakers"][user]
        save_users(users)
        return cfg['intent']['user'][language]['delete_success'].format(user)
    return cfg['intent']['user'][language]['delete_error'].format(user)

@register_call("change_spkid_user")
def change_spkid_user(session_id="general", user=None):
    cfg, language = __read_config__()
    users = load_users()
    if user not in users["speakers"]:
        return cfg['intent']['user'][language]['user_noexist'].format(user)

    logger.info(f"Aktualisiere Sprachprofil für {user}.")
    voice_sample = global_variables.voice_assistant.capture_voice_sample()
    if voice_sample:
        embedding = encoder.embed_utterance(voice_sample).tolist()
        users["speakers"][user]["voice"] = embedding
        save_users(users)
        return cfg['intent']['user'][language]['change_spkid_success'].format(user)
    return cfg['intent']['user'][language]['change_error'].format(user)