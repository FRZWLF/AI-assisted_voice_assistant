import json
import re
from datetime import datetime, timedelta
from chatbot import register_call
from dateutil.relativedelta import relativedelta

import global_variables
import os
import random
import yaml
from loguru import logger
from transformers import MarianMTModel, MarianTokenizer
from typing import Sequence
from words2num import w2n

from dateutil.parser import parse
from num2words import num2words
from tinydb import TinyDB, Query


class Translator:
    def __init__(self, source_lang: str, dest_lang: str) -> None:
        self.model_name = f'Helsinki-NLP/opus-mt-{source_lang}-{dest_lang}'
        self.model = MarianMTModel.from_pretrained(self.model_name)
        self.tokenizer = MarianTokenizer.from_pretrained(self.model_name)

    def translate(self, texts: Sequence[str]) -> Sequence[str]:
        tokens = self.tokenizer(list(texts), return_tensors="pt", padding=True)
        translate_tokens = self.model.generate(**tokens)
        return [self.tokenizer.decode(t, skip_special_tokens=True) for t in translate_tokens]


# Initialisiere Datenbankzugriff auf Modulebene
reminder_db_path = os.path.join('intents','functions','reminder','reminder_timer_db.json')
reminder_db = TinyDB(reminder_db_path)
reminder_table = reminder_db.table('reminder')

# Lade die Config global
CONFIG_PATH = os.path.join('intents','functions','reminder','config_reminder_timer.yml')

def __read_config__():
    cfg = None
    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


# Wir führen ein, dass die Callback Funktion eines Moduls immer 'callback' heißen muss.
def callback(processed=False):
    cfg, language = __read_config__()

    all_reminders = reminder_table.all()
    for r in all_reminders:
        parsed_time = parse(r['time'], fuzzy=True)
        now = datetime.now(parsed_time.tzinfo)
        # Ist der aktuelle Datenbankeintrag vor/gleich der jetzigen Zeit?
        if parsed_time <= now:
            res = ''

            # Ist der Sprecher bei Eingabe des Reminders bekannt gewesen?
            if r['speaker']:
                res += r['speaker'] + ' '

            # Wie ist der Satz formuliert worden?
            if r['kind'] == 'inf':
                REMINDER_TEXT = random.choice(cfg['intent']['reminder'][language]['execute_reminder_infinitive'])
                REMINDER_TEXT = REMINDER_TEXT.format(r['msg'])
                res += REMINDER_TEXT
            elif r['kind'] == 'to':
                REMINDER_TEXT = random.choice(cfg['intent']['reminder'][language]['execute_reminder_to'])
                REMINDER_TEXT = REMINDER_TEXT.format(r['msg'])
                res += REMINDER_TEXT
            elif r['kind'] in ['hour', 'minute', 'second']:
                if r['name'] is None:
                    TIMER_TEXT = random.choice(cfg['intent']['timer'][language]['execute_timer'])
                    TIMER_TEXT = TIMER_TEXT
                    res += TIMER_TEXT
                else:
                    TIMER_TEXT = random.choice(cfg['intent']['timer'][language]['execute_named_timer'])
                    TIMER_TEXT = TIMER_TEXT.format(r['name'])
                    res += TIMER_TEXT
            else:
                REMINDER_TEXT = random.choice(cfg['intent']['reminder'][language]['execute_reminder'])
                res += REMINDER_TEXT

            # Lösche den Eintrag falls die Erinnerung gesprochen werden konnte
            if processed:
                Reminder_Query = Query()
                # Überprüfen, ob es sich um einen Timer oder einen Reminder handelt
                if r['kind'] in ['hour', 'minute', 'second']:
                    logger.info('Der Timer für {} am {} mit mit einer Dauer von {} wird nun gelöscht.', r['speaker'], r['time'], r['duration'])
                    reminder_table.remove(Reminder_Query.speaker == r['speaker'] and Reminder_Query.time == r['time'] and Reminder_Query.kind == r['kind'] and Reminder_Query.duration == r['duration'] and Reminder_Query.name == r['name'])
                else:
                    # Entfernen für Reminder-Einträge
                    logger.info('Der Reminder für {} am {} mit Inhalt {} wird nun gelöscht.', r['speaker'], r['time'], r['msg'])
                    reminder_table.remove(Reminder_Query.speaker == r['speaker'] and Reminder_Query.time == r['time'] and Reminder_Query.msg == r['msg'] and Reminder_Query.kind == r['kind'])
                return None
            else:
                return res

    return None

def spoken_date(datetime, lang):
    hours = str(datetime.hour)
    minutes = "" if datetime.minute == 0 else str(datetime.minute)
    day = num2words(datetime.day, lang=lang, to="ordinal")
    month = num2words(datetime.month, lang=lang, to="ordinal")
    year = "" if datetime.year == datetime.now().year else str(datetime.year)

    # Anpassung an den deutschen Casus
    if lang == 'de':
        day += 'n'
        month += 'n'

    return hours, minutes, day, month, year

def spoken_timer(datetime):
    hours = int(datetime.hour)
    minutes = 0 if datetime.minute == 0 else int(datetime.minute)
    seconds = 0 if datetime.second == 0 else int(datetime.second)

    return hours, minutes, seconds

def convert_to_second_person(text):
    # Wörter für erste Person zu zweite Person konvertieren
    replacements = {
        "mein ": "dein ",
        "meine ": "deine ",
        "meinen ": "deinen ",
        "meinem ": "deinem ",
        "meiner ": "deiner ",
        "meines ": "deines ",
    }
    for key, value in replacements.items():
        text = re.sub(rf"\b{key}\b", value, text, flags=re.IGNORECASE)
    return text

@register_call("timer_list")
def timer_list(session_id:"general", dummy=0):
    cfg, language = __read_config__()

    # Hole den aktuellen Sprecher
    speaker = global_variables.voice_assistant.current_speaker

    # Hole alle Timer aus der Datenbank
    all_timers = reminder_table.search(Query().kind.one_of(["hour", "minute", "second"]) & (Query().speaker == speaker))
    now = datetime.now()

    # Erstelle eine Liste, um den Status jedes Timers zu speichern
    timer_status_list = []

    for t in all_timers:
        timer_time = parse(t['time'], fuzzy=True)
        time_remaining = timer_time - now

        # Berechne verbleibende Stunden, Minuten und Sekunden
        hours, remainder = divmod(time_remaining.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)

        # Konvertiere verbleibende Zeit in einen lesbaren String
        if hours > 0:
            time_string = f"{int(hours)} Stunden {int(minutes)} Minuten"
        elif minutes > 0:
            time_string = f"{int(minutes)} Minuten {int(seconds)} Sekunden"
        else:
            time_string = f"{int(seconds)} Sekunden"

        # Timer-Beschreibung erstellen
        if t['name'] is None:
            timer_description = f"Timer für {t['duration']}: Verbleibende Zeit: {time_string} "
        else:
            timer_description = f"Timer {t['name']} für {t['duration']}: Verbleibende Zeit: {time_string} "
        timer_status_list.append(timer_description)

    # Kombiniere alle Timer-Beschreibungen in eine Nachricht
    result = "\n".join(timer_status_list) if timer_status_list else "Keine aktiven Timer gefunden."
    return result


@register_call("timer")
def timer(session_id:"general", timer_data=None):
    cfg, language = __read_config__()

    logger.info("Data: {}", timer_data)

    # Split by the chosen delimiter
    args = timer_data.split("|")

    # Assign values, handling cases where parts might be missing
    name = args[0].strip() if len(args) > 0 and args[0].strip() else None
    timer = args[1].strip() if len(args) > 1 and args[1].strip() else None

    logger.info('Name said: {}.', name)
    logger.info('Timer said: {}.', timer)

    # Hole den aktuellen Sprecher, falls eine persönliche Erinnerung stattfinden soll
    speaker = global_variables.voice_assistant.current_speaker

    NO_TIMER_GIVEN = random.choice(cfg['intent']['timer'][language]['no_timer_given'])

    # Bereite das Ergebnis vor
    result = ""
    if speaker:
        result = speaker + ', '

    # Wurde keine Zeit angegeben?
    if not timer:
        return result + NO_TIMER_GIVEN

    marian_de_en = Translator(language, 'en')
    timer = marian_de_en.translate([timer])[0].lower()
    logger.info('Timer in en said: {}.', timer)


    word_str = timer.split(" ")
    words2num_res = ""
    for i in word_str:
        try:
            words2num_res += str(w2n(i)) + " "
        except:
            words2num_res += i + " "
    timer = words2num_res
    logger.info("words2num: {}", timer)

    hours, minutes, seconds = 0,0,0

    match = re.search(r"(\d+)\s*(hours|hour|minutes|minute|seconds|second)", timer)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit == "hours" or unit == "hour":
            target_date = (datetime.now() + timedelta(hours=amount)).strftime('%Y-%m-%d %H:%M:%S')
            hours = amount
        elif unit == "minutes" or unit == "minute":
            target_date = (datetime.now() + timedelta(minutes=amount)).strftime('%Y-%m-%d %H:%M:%S')
            minutes = amount
        elif unit == "seconds" or unit == "second":
            target_date = (datetime.now() + timedelta(seconds=amount)).strftime('%Y-%m-%d %H:%M:%S')
            seconds = amount
        timer = re.sub(r"(\d+)\s*(hours|hour|minutes|minute|seconds|second)", target_date, timer, count=1)

    logger.info("timer: {}", timer)

    parsed_timer = parse(timer, fuzzy=True)
    logger.info('Parsed Timer: {}.', parsed_timer)


    # Zielzeit berechnen
    final_time = parsed_timer.strftime('%Y-%m-%d %H:%M:%S')
    logger.info("Final reminder datetime: {}", parsed_timer)


    result = ""
    if name is None:
        logger.info('Name: {}.', name)
        if hours > 0:
            TIMER_HOURS = random.choice(cfg['intent']['timer'][language]['timer_hour'])
            TIMER_HOURS = TIMER_HOURS.format(hours)
            result = result + " " + TIMER_HOURS
            reminder_table.insert({'time': final_time, 'kind': 'hour', 'duration': f"{hours} Stunden", 'name': name, 'speaker':speaker})
        elif minutes > 0:
            TIMER_MINUTES = random.choice(cfg['intent']['timer'][language]['timer_minute'])
            TIMER_MINUTES = TIMER_MINUTES.format(minutes)
            result = result + " " + TIMER_MINUTES
            reminder_table.insert({'time': final_time, 'kind': 'minute', 'duration': f"{minutes} Minuten", 'name': name, 'speaker':speaker})
        elif seconds > 0:
            TIMER_SECONDS = random.choice(cfg['intent']['timer'][language]['timer_second'])
            TIMER_SECONDS = TIMER_SECONDS.format(seconds)
            result = result + " " + TIMER_SECONDS
            reminder_table.insert({'time': final_time, 'kind': 'second', 'duration': f"{seconds} Sekunden", 'name': name, 'speaker':speaker})

        logger.info("Timer gesetzt auf: {}", result)
    else:
        logger.info('Name: {}.', name)
        if hours > 0:
            TIMER_HOURS = random.choice(cfg['intent']['timer'][language]['named_timer_hour'])
            TIMER_HOURS = TIMER_HOURS.format(name, hours)
            result = result + " " + TIMER_HOURS
            reminder_table.insert({'time': final_time, 'kind': 'hour', 'duration': f"{hours} Stunden", 'name': name, 'speaker':speaker})
        elif minutes > 0:
            TIMER_MINUTES = random.choice(cfg['intent']['timer'][language]['named_timer_minute'])
            TIMER_MINUTES = TIMER_MINUTES.format(name, minutes)
            result = result + " " + TIMER_MINUTES
            reminder_table.insert({'time': final_time, 'kind': 'minute', 'duration': f"{minutes} Minuten", 'name': name, 'speaker':speaker})
        elif seconds > 0:
            TIMER_SECONDS = random.choice(cfg['intent']['timer'][language]['named_timer_second'])
            TIMER_SECONDS = TIMER_SECONDS.format(name, seconds)
            result = result + " " + TIMER_SECONDS
            reminder_table.insert({'time': final_time, 'kind': 'second', 'duration': f"{seconds} Sekunden", 'name': name, 'speaker':speaker})

        logger.info("Timer {} gesetzt auf: {}", name, result)

    return result


#multiple parameters don't work: time,reminder_to, reminder_infinitive
#workaround by splitting
@register_call("reminder")
def reminder(session_id="general", reminder_data=None):
    cfg, language = __read_config__()

    logger.info("Data: {}", reminder_data)

    # Split by the chosen delimiter
    args = reminder_data.split("|")

    # Assign values, handling cases where parts might be missing
    time = args[0].strip() if len(args) > 0 and args[0].strip() else None
    reminder_to = args[1].strip() if len(args) > 1 and args[1].strip() else None
    reminder_infinitive = args[2].strip() if len(args) > 2 and args[2].strip() else None


    #Wörterbuch
    months = {
        "januar": "01", "februar": "02", "märz": "03", "april": "04", "mai": "05", "juni": "06",
        "juli": "07", "august": "08", "september": "09", "oktober": "10", "november": "11", "dezember": "12"
    }

    ordinal_days = {
        "ersten": "1", "zweiten": "2", "dritten": "3", "vierten": "4", "fünften": "5", "sechsten": "6",
        "siebten": "7", "siebenten": "7", "achten": "8", "neunten": "9", "zehnten": "10", "elften": "11", "zwölften": "12",
        "dreizehnten": "13", "vierzehnten": "14", "fünfzehnten": "15", "sechzehnten": "16", "siebzehnten": "17",
        "achtzehnten": "18", "neunzehnten": "19", "zwanzigsten": "20", "einundzwanzigsten": "21",
        "zweiundzwanzigsten": "22", "dreiundzwanzigsten": "23", "vierundzwanzigsten": "24",
        "fünfundzwanzigsten": "25", "sechsundzwanzigsten": "26", "siebenundzwanzigsten": "27",
        "achtundzwanzigsten": "28", "neunundzwanzigsten": "29", "dreißigsten": "30", "einunddreißigsten": "31",
    }

    # Hole den aktuellen Sprecher, falls eine persönliche Erinnerung stattfinden soll
    speaker = global_variables.voice_assistant.current_speaker

    NO_TIME_GIVEN = random.choice(cfg['intent']['reminder'][language]['no_time_given'])
    INVALID_TIME_GIVEN = random.choice(cfg['intent']['reminder'][language]['invalid_time_given'])

    # Bereite das Ergebnis vor
    result = ""
    if speaker:
        result = speaker + ', '

    # Wurde keine Uhrzeit angegeben?
    if not time:
        return result + NO_TIME_GIVEN


    # Konvertiere den Monat
    for month_name, month_num in months.items():
        time = re.sub(r"\b" + month_name + r"\b", month_num, time, flags=re.IGNORECASE)

    # Konvertiere die Ordnungszahlen für Tage
    for day_name, day_num in ordinal_days.items():
        time = re.sub(r"\b" + day_name + r"\b", day_num, time, flags=re.IGNORECASE)


    date_match = re.search(r"\b(\d{1,2})\s+(\d{1,2})\b", time)
    if date_match:
        day = date_match.group(1).zfill(2)
        month = date_match.group(2).zfill(2)
        current_year = str(datetime.now().year)
        formatted_date = f"{current_year}-{month}-{day}"
        time = re.sub(r"\b(\d{1,2})\s+(\d{1,2})\b", formatted_date, time, count=1)
    logger.info("Time: {}", time)


    time = re.sub(r"\bein Uhr\b", "1 Uhr", time)
    time = re.sub(r"\bzwei Uhr\b", "2 Uhr", time)
    #Translation to "EN" before parsing into parse() for the best result
    marian_de_en = Translator(language, 'en')
    time = marian_de_en.translate([time])[0].lower()
    time = re.sub(r"\ba watch\b", "1 o'clock", time)
    time = re.sub(r"\bone watch\b", "1 o'clock", time)
    logger.info('Time in en said: {}.', time)
    time = re.sub(r",", "", time)

    #BUG-FIX: 8 o'clock 8 | 18 o'clock 18 cus of some issues with en-translation
    # Suche nach dem zweiten Auftreten von „o'clock“ und schneide den String dort ab
    occurrences = [m.start() for m in re.finditer(r"o'clock", time)]
    if len(occurrences) > 1:
        time = time[:occurrences[1]]  # String bis zum zweiten "o'clock" kürzen


    word_str = time.split(" ")
    words2num_res = ""
    for i in word_str:
        try:
            words2num_res += str(w2n(i)) + " "
        except:
            words2num_res += i + " "
    time = words2num_res
    logger.info("words2num: {}", time)
    time = re.sub(r"(\d{1,2} o'clock), (\d+)", r"\1 \2", time)
    logger.info('Time in en said (formatted): {}.', time)

    #Change german terms "übermorgen" und "morgen" to exact dates so that parse() can handle those
    if "the day after tomorrow" in time:
        time = re.sub("the day after tomorrow", (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d'), time)
    if "tomorrow" in time:
        time = re.sub("tomorrow", (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'), time)
    if "today" in time:
        time = re.sub("today", datetime.now().strftime('%Y-%m-%d'), time)

    #Change expression "in ... Tagen" to exact dates so that parse() can handle those
    hastarget = False
    match = re.search(r"(\d+)\s*(years|year|months|month|weeks|week|days|day|hours|hour|minutes|minute)", time)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit == "years" or unit == "year":
            target_date = (datetime.now() + relativedelta(years=amount)).strftime('%Y-%m-%d')
        elif unit == "months" or unit == "month":
            target_date = (datetime.now() + relativedelta(months=amount)).strftime('%Y-%m-%d')
        elif unit == "weeks" or unit == "week":
            target_date = (datetime.now() + timedelta(weeks=amount)).strftime('%Y-%m-%d')
        elif unit == "days" or unit == "day":
            target_date = (datetime.now() + timedelta(days=amount)).strftime('%Y-%m-%d')
        elif unit == "hours" or unit == "hour":
            target_date = (datetime.now() + timedelta(hours=amount)).strftime('%Y-%m-%d %H:%M')
            hastarget = True
        elif unit == "minutes" or unit == "minute":
            target_date = (datetime.now() + timedelta(minutes=amount)).strftime('%Y-%m-%d %H:%M')
            hastarget = True
        time = re.sub(r"(\d+)\s*(years|year|months|month|weeks|week|days|day|hours|hour|minutes|minute)", target_date, time, count=1)


    #Extract the date and remove it temporarily to avoid confusion during time matching
    date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", time)
    date_part = date_match.group(0) if date_match else ""
    time = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", time).strip()


    # Standardisiere "o'clock" zu am/pm anhand der angegebenen Zeit
    if not hastarget:
        match = re.search(r"\b(\d{1,2})(?:\s*o'clock)?(?:\s+(\d{1,2}))?\b", time)
        if match:
            hour = int(match.group(1))
            logger.info("hour: {}", hour)
            minutes = match.group(2) if match.group(2) else "00"
            logger.info("minutes: {}", minutes)
            if hour >= 24:
                return result + INVALID_TIME_GIVEN
            else:
                if hour < 12:
                    formatted_time = f" {hour}:{minutes} am"
                elif hour == 12:
                    formatted_time =  f" {hour}:{minutes} pm"
                else:
                    hour -= 12
                    formatted_time = f" {hour}:{minutes} pm"
            time = re.sub(r"\b(\d{1,2})(?:\s*o'clock)?(?:\s+(\d{1,2}))?\b", formatted_time, time, count=1)
        else:
            # Wenn keine Uhrzeit gefunden wird, aktuelle Zeit nehmen
            current_time = datetime.now().strftime('%H:%M')
            time += f" {current_time}"


    #Add the date and time together
    time = f"{date_part} {time}".strip()


    logger.info('Time said: {}.', time)
    logger.info('Reminder to said: {}.', reminder_to)
    logger.info('Reminder infinitive said: {}.', reminder_infinitive)
    # Wir machen uns das Parsing des Datums-/Zeitwertes leicht
    parsed_time = parse(time, fuzzy=True)
    logger.info('Parsed Time: {}.', parsed_time)

    # Überprüfen auf vergangene Daten und Uhrzeiten
    now = datetime.now()
    if parsed_time < now:
        if parsed_time.date() < now.date():
            # Setze auf nächstes Jahr, wenn Datum vergangen
            parsed_time = parsed_time.replace(year=now.year + 1)
        elif parsed_time.time() < now.time():
            # Setze auf nächsten Tag, wenn Uhrzeit vergangen
            parsed_time += timedelta(days=1)

    final_time = parsed_time.strftime('%Y-%m-%d %H:%M:%S')
    logger.info("Final reminder datetime: {}", parsed_time)

    # Generiere das gesprochene Datum
    hours, minutes, day, month, year = spoken_date(parsed_time, language)
    logger.info('Hours: {} Minutes: {} Day: {} Month: {} Year: {}.', hours, minutes,day,month, year)

    if reminder_to is not None:
        reminder_to = convert_to_second_person(reminder_to)

    # Am selben Tag wie heute?
    if datetime.now().date() == parsed_time.date():
        if reminder_to:
            SAME_DAY_TO = random.choice(cfg['intent']['reminder'][language]['reminder_same_day_to'])
            SAME_DAY_TO = SAME_DAY_TO.format(hours, minutes, reminder_to)
            result = result + " " + SAME_DAY_TO
            reminder_table.insert({'time':final_time, 'kind':'to', 'msg':reminder_to, 'speaker':speaker})
        elif reminder_infinitive:
            SAME_DAY_INFINITIVE = random.choice(cfg['intent']['reminder'][language]['reminder_same_day_infinitive'])
            SAME_DAY_INFINITIVE = SAME_DAY_INFINITIVE.format(hours, minutes, reminder_infinitive)
            result = result + " " + SAME_DAY_INFINITIVE
            reminder_table.insert({'time':final_time, 'kind':'inf', 'msg':reminder_infinitive, 'speaker':speaker})
        else:
            # Es wurde nicht angegeben, an was erinnert werden soll
            logger.info('Time Today without action!')
            SAME_DAY_NO_ACTION = random.choice(cfg['intent']['reminder'][language]['reminder_same_day_no_action'])
            SAME_DAY_NO_ACTION = SAME_DAY_NO_ACTION.format(hours, minutes)
            result = result + " " + SAME_DAY_NO_ACTION
            reminder_table.insert({'time':final_time, 'kind':'none', 'msg':'', 'speaker':speaker})
    else:
        if reminder_to:
            TO = random.choice(cfg['intent']['reminder'][language]['reminder_to'])
            TO = TO.format(day, month, year, hours, minutes, reminder_to)
            result = result + " " + TO
            reminder_table.insert({'time':final_time, 'kind':'to', 'msg':reminder_to, 'speaker':speaker})
        elif reminder_infinitive:
            INFINITIVE = random.choice(cfg['intent']['reminder'][language]['reminder_infinitive'])
            INFINITIVE = INFINITIVE.format(day, month, year, hours, minutes, reminder_infinitive)
            result = result + " " + INFINITIVE
            reminder_table.insert({'time':final_time, 'kind':'inf', 'msg':reminder_infinitive, 'speaker':speaker})
        else:
            # Es wurde nicht angegeben, an was erinnert werden soll
            logger.info('Time NOT Today without action!')
            NO_ACTION = random.choice(cfg['intent']['reminder'][language]['reminder_no_action'])
            NO_ACTION = NO_ACTION.format(day, month, year, hours, minutes)
            result = result + " " + NO_ACTION
            reminder_table.insert({'time':final_time, 'kind':'none', 'msg':'', 'speaker':speaker})

    logger.info("Reminder mit Inhalt {} erkannt.", result)

    return result