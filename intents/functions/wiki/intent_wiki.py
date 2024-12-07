from loguru import logger
from chatbot import register_call

import constants
import global_variables
import yaml
import random
import os
import wikipedia


CONFIG_PATH = constants.find_data_file(os.path.join('intents','functions','wiki','config_wiki.yml'))
def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


@register_call("wiki")
def wiki(session_id = "general", query="none"):
    cfg, language = __read_config__()
    if language:
        wikipedia.set_lang(language)

    UNKNOWN_ENTITY = random.choice(cfg['intent']['wiki'][language]['unknown_entity']).format(query)

    session_state = getattr(global_variables, "wiki_state", None)
    if session_state is None:
        session_state = global_variables.wiki_state = {
            "step": 0,
            "query": query.strip(),
        }

    if session_state["step"] == 0:
        global_variables.voice_assistant.is_listening = False
        try:
            # Suche den Artikel und gib eine strukturierte Antwort
            summary = wikipedia.summary(session_state["query"], sentences=2)
            session_state["step"] += 1
            global_variables.context = more_wiki
            return random.choice(cfg['intent']['wiki'][language]['answer']).format(summary)

        except wikipedia.exceptions.DisambiguationError as e:
            alternatives = ", ".join(e.options[:5])  # Zeige die ersten 5 Alternativen
            return random.choice(cfg['intent']['wiki'][language]['alternativ']).format(alternatives)
        except wikipedia.exceptions.PageError:
            # Suche alternative Artikel
            for new_query in wikipedia.search(query):
                try:
                    summary = wikipedia.summary(new_query, sentences=2)
                    session_state["query"] = new_query  # Aktualisiere die Anfrage
                    session_state["step"] += 1
                    global_variables.context = "more_wiki"
                    return random.choice(cfg['intent']['wiki'][language]['answer']).format(summary)
                except Exception as alt_exception:
                    logger.warning(f"Fehler bei Alternativsuche: {alt_exception}")
            return UNKNOWN_ENTITY
        except Exception as e:
            logger.error(f"Fehler bei Wikipedia-Anfrage: {e}")
        return UNKNOWN_ENTITY


def more_wiki(user_input=''):
    if not global_variables.voice_assistant.is_listening:
        global_variables.voice_assistant.is_listening = True
    session_state = getattr(global_variables, "wiki_state", None)
    cfg, language = __read_config__()
    if language:
        wikipedia.set_lang(language)

    UNKNOWN_ENTITY = random.choice(cfg['intent']['wiki'][language]['unknown_entity']).format(session_state["query"])
    if not session_state:
        return cfg['intent']['wiki'][language]['no_session']

    if session_state["step"] == 1:
        user_input = user_input.strip().lower()
        if user_input in cfg['intent']['wiki'][language]['yes_answers']:
            try:
                summary = wikipedia.summary(session_state["query"], sentences=10)
                global_variables.wiki_state = None
                global_variables.context = None
                return random.choice(cfg['intent']['wiki'][language]['more_answer']).format(summary)
            except Exception as e:
                logger.error(f"Fehler bei längerer Wikipedia-Anfrage: {e}")
                global_variables.wiki_state = None
                global_variables.context = None
                return UNKNOWN_ENTITY

        elif user_input in cfg['intent']['wiki'][language]['no_answers']:
            global_variables.wiki_state = None
            global_variables.context = None
            return random.choice(cfg['intent']['wiki'][language]['standard'])

        else:
            return random.choice(cfg['intent']['wiki'][language]['unclear_input'])