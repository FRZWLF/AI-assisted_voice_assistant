import os
import random
import yaml
from chatbot import register_call
import constants
import global_variables
from loguru import logger


@register_call("animalSound")
def animalSound(session_id="general", animal="none"):
    config_path = constants.find_data_file(os.path.join('intents', 'functions', 'animalsounds', 'config_animalsounds.yml'))
    ogg_path = constants.find_data_file(os.path.join('intents', 'functions', 'animalsounds', 'animals'))

    cfg = None
    with open(config_path, 'r', encoding="utf-8") as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

        if not cfg:
            logger.error("Konnte Konfiguration fuer animalsounds nicht lesen.")
            return ""

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    ANIMAL_UNKOWN = random.choice(cfg['intent']['animalsounds'][LANGUAGE]['animal_not_found'])

    animals = {}
    for key, value in cfg['intent']['animalsounds']['animals'].items():
        animals[key] = value

    for a in animals:
        if animal.strip().lower() in animals[a]:
            ogg_file = os.path.join(ogg_path, a + '.ogg')
            # if mixer.music.get_busy():
            #     mixer.music.stop()
            # mixer.music.load(ogg_file)
            # mixer.music.play()
            global_variables.voice_assistant.audio_player.play_file(ogg_file)
            return ""

    return ANIMAL_UNKOWN
