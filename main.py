import os
import random
import sys
import threading
import time
import pvporcupine
from loguru import logger
import multiprocessing
from scipy.io.wavfile import write
from TTS import Voice
import yaml
import struct
import pyaudio
import sounddevice as sd
from vosk import Model, SpkModel, KaldiRecognizer
import json
import numpy as np

from download_app import DownloadApp
from marianMTModels import download_translation_models
from langmgmt import LanguageManager
from usermgmt import UserMgmt
from intentmgmt import IntentManagement
from audioplayer import AudioPlayer
import wx.adv
import wx
import constants
import global_variables
from notification import Notification
from resemblyzer import VoiceEncoder
from resemblyzer.audio import preprocess_wav

from vosk_model_downloader import download_vosk_model, download_all_vosk_models, VOSK_MODELS

# GUI-Anwendung mit pythonw main.py starten

CONFIG_FILE = constants.find_data_file("config.yml")


class TaskBarIcon(wx.adv.TaskBarIcon):

    def __init__(self, frame, download_manager=None):
        self.frame = frame
        self.download_manager = download_manager
        super(TaskBarIcon, self).__init__()
        self.set_icon(constants.TRAY_ICON_INITIALIZING, constants.TRAY_TOOLTIP + ": Initialisiere ...")

    def create_menu_item(self, menu, label, func):
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.Append(item)
        return item

    def create_popup_menu(self):
        menu = wx.Menu()
        self.create_menu_item(menu, 'Beenden', self.on_exit)
        return menu

    def set_icon(self, path, tooltip=constants.TRAY_TOOLTIP):
        icon = wx.Icon(path)
        self.SetIcon(icon, tooltip)

    def on_exit(self, event):
        # logger.info("on_exit wurde aufgerufen.")

        if global_variables.voice_assistant:
            global_variables.voice_assistant.terminate()

        # Debugging für Download Manager
        # if hasattr(self.frame, "download_manager"):
            # logger.info(f"Frame hat download_manager: {self.frame.download_manager}")
        # else:
            # logger.warning("Frame hat kein download_manager Attribut!")

        # Beende den Download Manager
        if hasattr(self.frame, "download_manager") and self.frame.download_manager:
            logger.info("Schließe Download Manager...")
            try:
                self.frame.download_manager.on_close_window(None)
            except Exception as e:
                logger.error(f"Fehler beim Schließen des Download Managers: {e}")
        else:
            logger.info("Ich kann nicht sauber beenden!")

        wx.CallAfter(self.Destroy)
        self.frame.Close()


class MainApp(wx.App):
    def OnInit(self):
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        self.download_manager = DownloadApp(downloads={lang: 0 for lang in VOSK_MODELS}, clearSigInt=False, redirect=True, filename='log.txt')
        frame.download_manager = self.download_manager
        self.icon = TaskBarIcon(frame, frame.download_manager)
        logger.info("DownloadManager initialisiert")
        self.Bind(wx.EVT_CLOSE, self.on_close_window)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update, self.timer)
        return True

    def update(self, event):
        if self.download_manager and self.download_manager.all_downloads_done:
            logger.info("DownloadManager abgeschlossen. Entferne Instanz.")
            self.download_manager = None

        if global_variables.voice_assistant:
            global_variables.voice_assistant.loop()

    def on_close_window(self, evt):
        if self.icon:
            logger.info("Beende TaskBarIcon...")
            self.icon.on_exit(evt)
        self.icon.Destroy()

        evt.skip()


class VoiceAssistant():

    def __init__(self):

        logger.info("Initialisiere VoiceAssistant...")

        self.app = MainApp(clearSigInt=False, redirect=True, filename='log.txt')

        # Referenziere den Download-Manager aus der MainApp
        self.download = self.app.download_manager

        logger.debug("Lese Konfiguration...")

        global CONFIG_FILE
        with open(CONFIG_FILE, 'r', encoding="utf-8") as ymlfile:
            self.cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

        if self.cfg:
            logger.debug("Konfiguration erfolgreich gelesen.")
        else:
            logger.error("Konfiguration konnte nicht gelesen werden.")
            sys.exit(1)

        # Listen von Root-Objekten mit wiederum einer Liste von Objekten
        language = self.cfg['assistant']['language']
        logger.info(f"Sprache {language}")
        if not language:
            language = "de"
        logger.info(f"Verwende Sprache {language}")

        self.lang_manager = LanguageManager(language=language)

        # Starte den Modell-Download
        download_translation_models()

        self.show_balloon = self.cfg['assistant']['show_balloon']

        logger.debug("Initialisiere Wake Word Erkennung...")
        self.wake_words = self.cfg["assistant"]["wakewords"]
        if not self.wake_words:
            self.wake_words = ['americano']
        logger.debug("Wake Words sind {}" ','.join(self.wake_words))
        self.porcupine = pvporcupine.create(keywords=self.wake_words, sensitivities=[0.6, 0.6])
        logger.info("Wake Words Erkennung wurde initialisiert.")

        # Audio-Stream needed
        logger.info("Initialisiere Audioeingabe...")
        self.pa = pyaudio.PyAudio()

        # Verfügbare Geräte abrufen
        devices = sd.query_devices()
        default_device = sd.default.device['input']

        # Aktuelles Standardgerät finden
        if default_device is not None:
            logger.info(f"Standard-Mikrofon: {devices[default_device]['name']}")
            self.audio_stream = self.pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length,
                input_device_index=default_device
            )
        else:
            logger.warning("Kein Standard-Mikrofon gefunden.")
        logger.info("Audiostream geöffnet...")

        # Lese Lautstärke
        self.volume = self.cfg["assistant"]["volume"]
        self.silenced_volume = self.cfg["assistant"]["silenced_volume"]

        logger.info("Voice Assistant wird initialisiert...")
        self.tts = Voice()

        self.encoder = VoiceEncoder()

        #####       Voices       #####
        self.available_voices = {}
        # Mehrstimm- und Mehrsprachunterstützung
        self.load_available_languages()

        # Sprache und Stimme setzen
        if language in self.available_voices and self.available_voices[language]:
            chosen_voice = random.choice(self.available_voices[language])
            self.tts.set_voice(chosen_voice)
            logger.info(f"Stimme {chosen_voice} für Sprache {language} gesetzt.")
        else:
            logger.warning("Standardstimme wird verwendet.")
        self.tts.set_volume(self.volume)
        self.say_with_language(self.tts, self.lang_manager, "intent.tts.initial")

        # Benachrichtigung anzeigen
        if self.show_balloon:
            Notification.show('Initialisierung', 'Sprachausgabe aktiviert', ttl=4000)
        logger.debug("Voice Assistant initialisiert")

        logger.info("Initialisiere Spracherkennung...")
        self.say_with_language(self.tts, self.lang_manager, "intent.tts.initial_voice_recognition_start")
        # Lade das Speaker-Modell (benötigt für alle Sprachen)
        speaker_model_path = download_vosk_model("spk", self.download)
        s2t_model_path = download_vosk_model(language, self.download)

        s2t_model = Model(s2t_model_path)
        speaker_model = SpkModel(speaker_model_path)
        self.rec = KaldiRecognizer(s2t_model, 16000, speaker_model)
        self.is_listening = False

        logger.info("Lade andere Modelle im Hintergrund...")
        background_thread = threading.Thread(target=download_all_vosk_models, args=(language, self.download), daemon=True)
        background_thread.start()

        self.say_with_language(self.tts, self.lang_manager, "intent.tts.initial_voice_recognition_end")
        logger.info("Spracherkennung initialisiert.")

        logger.info("Initialisiere Benutzerverwaltung...")
        self.cfg['assistant']['user_initialized'] = check_user_initialization()
        # Prüfen, ob Nutzer initialisiert sind
        if not self.cfg['assistant'].get('user_initialized', False):
            logger.info("Kein initialer Benutzer gefunden. Sample-User wird erstellt...")
            self.user_management = UserMgmt(init_dummies=True)
        else:
            logger.info("Benutzer bereits initialisiert.")
            self.user_management = UserMgmt()
        self.allow_only_known_speakers = self.cfg['assistant']['allow_only_known_speakers']
        logger.info("Benutzerverwaltung initialisiert.")

        self.audio_player = AudioPlayer()
        self.audio_player.set_volume(self.volume)

        logger.info("Initialisiere Intent Management...")
        self.intent_management = IntentManagement(self.lang_manager)
        logger.info("{} Intents gefunden.", self.intent_management.get_count())
        logger.info("Intent Management wurde aus initialisiert.")

        # Erzeuge eine Liste, die die Callback Funktionen vorhält
        self.callbacks = self.intent_management.register_callbacks()
        logger.info('{} callbacks gefunden', len(self.callbacks))
        if self.show_balloon:
            Notification.show('Initialisierung', 'Abgeschlossen', ttl=4000)

        self.app.icon.set_icon(constants.TRAY_ICON_IDLE, constants.TRAY_TOOLTIP + ": Bereit")
        timer_start_res = self.app.timer.Start(milliseconds=1, oneShot=wx.TIMER_CONTINUOUS)
        logger.debug("Timer gestartet? {}", timer_start_res)

        self.say_with_language(self.tts, self.lang_manager, "intent.tts.initial_setup_end")


    def __detectSpeaker__(self, input, short_sample_threshold=0.3, long_sample_threshold=0.5):
        """
        Erkennt den Sprecher basierend auf dem Eingabe-Sample.
        Unterschiedliche Schwellenwerte für kurze und lange Samples.
        """
        encoder = VoiceEncoder()
        try:
            # Verarbeite den Input
            if not isinstance(input, np.ndarray):
                input = np.array(input, dtype=np.float32)

            processed_wav = preprocess_wav(input)
            input_embedding = encoder.embed_utterance(processed_wav)
            # logger.debug(f"Input-Embedding: {input_embedding[:10]}...")
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der Sprachaufnahme: {e}")
            return "Unbekannt"

        best_speaker = "Unbekannt"
        best_cosine_similarity = -1

        # Wähle den Threshold basierend auf der Länge des Samples
        sample_length = len(processed_wav) / 16000  # Länge in Sekunden
        threshold = short_sample_threshold if sample_length < 2 else long_sample_threshold
        # logger.info(f"Verwendeter Ähnlichkeitsschwellenwert: {threshold}")

        # Vergleiche die Embeddings mit gespeicherten Stimmen
        for speaker in self.user_management.speaker_table.all():
            saved_embedding = speaker.get('voice')
            if saved_embedding is None:
                logger.debug(f"Überspringe '{speaker.get('name')}'.")
                return speaker.get('name')

            saved_embedding = np.array(saved_embedding, dtype=np.float32)
            cosine_similarity = np.dot(input_embedding, saved_embedding) / (
                    np.linalg.norm(input_embedding) * np.linalg.norm(saved_embedding)
            )
            logger.debug(f"Vergleich mit Speaker '{speaker.get('name')}' - Ähnlichkeit: {cosine_similarity:.3f}")
            if cosine_similarity > best_cosine_similarity and cosine_similarity > threshold:
                best_cosine_similarity = cosine_similarity
                best_speaker = speaker.get('name')

            if best_cosine_similarity >= threshold:
                logger.info(f"Erkannter Sprecher: {best_speaker} mit Ähnlichkeit {best_cosine_similarity:.3f}")
                return best_speaker
            else:
                logger.warning("Kein passender Sprecher erkannt.")
                return "Unbekannt"


    def capture_voice_sample(self, silence_duration=2):
        """
        Aufnahme und Verarbeitung eines Sprachsamples, das endet, sobald der Nutzer nicht mehr spricht.
        """
        logger.info(f"Starte Sprachaufnahme für Fingerabdruck.")

        try:
            # Sprachaufforderung ausgeben
            self.say_with_language(self.tts, self.lang_manager, "intent.tts.prompt_sentence")
            # Warten, bis TTS abgeschlossen ist
            while self.tts.is_busy():
                time.sleep(0.2)  # Vermeidet zu häufige Abfragen
            logger.info("TTS abgeschlossen. Starte Aufnahme.")


            # Aufnahmeparameter
            sample_rate = 16000
            silence_threshold = 0.01  # Lautstärkegrenze für "Stille"
            buffer = []
            silence_counter = 0

            with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
                blocksize = stream.blocksize or 1024
                while silence_counter < silence_duration * sample_rate // blocksize:
                    audio_data, _ = stream.read(blocksize)

                    # Prüfen auf leere Daten
                    if not audio_data.size:
                        logger.warning("Keine Daten erkannt, überspringe Block.")
                        continue

                    buffer.extend(audio_data.flatten())
                    if max(abs(audio_data)) < silence_threshold:
                        silence_counter += 1
                    else:
                        silence_counter = 0

            if len(buffer) < sample_rate * 1:  # Mindestens 1 Sekunde
                logger.error("Sprachaufnahme zu kurz. Wiederholen!")
                return None

            # Verarbeitung der Sprachaufnahme
            encoder = VoiceEncoder()
            wav_preprocessed = preprocess_wav(np.array(buffer), source_sr=sample_rate)
            fingerprint = encoder.embed_utterance(wav_preprocessed)
            logger.info(f"Fingerprint erfolgreich generiert. Länge: {len(fingerprint)}")

            # Nach der Aufnahme
            write("test_sample.wav", sample_rate, np.array(buffer))
            logger.info("Sprachaufnahme gespeichert: test_sample.wav")
            logger.info("Stimmfingerabdruck erfolgreich erstellt.")
            return fingerprint

        except Exception as e:
            logger.error(f"Fehler bei der Sprachaufnahme oder Verarbeitung: {e}")
            return None


    def load_available_languages(self):
        """Lädt die verfügbaren Sprachen und Stimmen aus einer YAML-Datei und aktualisiert diese, falls neue Sprachen hinzugefügt werden."""
        languages_file = constants.find_data_file('languages.yml')

        # Standardmäßig unterstützte Sprachen
        supported_languages = ['de', 'en', 'fr', 'es', 'it', 'ja', 'ru']

        # Prüfen, ob die Sprachdatei vorhanden ist, und laden
        if os.path.exists(languages_file):
            with open(languages_file, 'r', encoding='utf-8') as file:
                language_data = yaml.load(file, Loader=yaml.FullLoader) or {'languages': {}}
        else:
            language_data = {'languages': {}}

        # Aktualisiere für jede unterstützte Sprache die verfügbaren Stimmen
        updated = False
        for lang in supported_languages:
            voices = self.tts.get_voice_keys_by_language(lang)
            if voices:
                self.available_voices[lang] = voices
                language_data['languages'][lang] = voices
                updated = True
                logger.info(f"Verfügbare Stimmen für Sprache {lang}: {voices}")
            else:
                logger.warning(f"Keine Stimmen für Sprache {lang} gefunden.")

        # Speichere die aktualisierte Sprachliste, falls Änderungen vorliegen
        if updated:
            with open(languages_file, 'w', encoding='utf-8') as file:
                yaml.dump(language_data, file)


    def terminate(self):
        logger.debug("Beginne Aufräumarbeiten...")

        # Stoppe den Timer
        self.app.timer.Stop()

        # Speichern der Konfiguration
        global_variables.voice_assistant.cfg["assistant"]["volume"] = global_variables.voice_assistant.volume
        global_variables.voice_assistant.cfg["assistant"]["silenced_volume"] = global_variables.voice_assistant.silenced_volume
        global_variables.voice_assistant.cfg["assistant"]["language"] = global_variables.voice_assistant.cfg["assistant"]["language"]
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(global_variables.voice_assistant.cfg, f, default_flow_style=False, sort_keys=False)

        if global_variables.voice_assistant.porcupine:
            global_variables.voice_assistant.porcupine.delete()

        if global_variables.voice_assistant.audio_stream is not None:
            global_variables.voice_assistant.audio_stream.close()

        if global_variables.voice_assistant.audio_player is not None:
            global_variables.voice_assistant.audio_player.stop()

        if global_variables.voice_assistant.pa is not None:
            global_variables.voice_assistant.pa.terminate()


    def loop(self):
            pcm = global_variables.voice_assistant.audio_stream.read(global_variables.voice_assistant.porcupine.frame_length)
            pcm_unpacked = struct.unpack_from("h" * global_variables.voice_assistant.porcupine.frame_length, pcm)
            keyword_index = global_variables.voice_assistant.porcupine.process(pcm_unpacked)

            if keyword_index >= 0:
                logger.info("Wake Word {} erkannt.", global_variables.voice_assistant.wake_words[keyword_index])
                global_variables.voice_assistant.is_listening = True

            if global_variables.voice_assistant.is_listening:
                if not global_variables.voice_assistant.tts.is_busy():
                    self.app.icon.set_icon(constants.TRAY_ICON_LISTENING, constants.TRAY_TOOLTIP + ": Ich höre...")

                # Spielt derzeit Musik oder sonstiges Audio? Dann setze die Lautstärke runter
                if global_variables.voice_assistant.audio_player.is_playing():
                    global_variables.voice_assistant.audio_player.set_volume(global_variables.voice_assistant.silenced_volume)

                if global_variables.voice_assistant.rec.AcceptWaveform(pcm):
                    recResult = json.loads(global_variables.voice_assistant.rec.Result())
                    logger.info(f"Länge von recResult['spk']: {len(recResult['spk'])}")
                    logger.info("recResult {}", recResult)
                    speaker = global_variables.voice_assistant.__detectSpeaker__(recResult['spk'])
                    logger.info("Speaker: {}", speaker)

                    if (speaker is None) and (global_variables.voice_assistant.allow_only_known_speakers is True):
                        logger.info("Ich kenne deine Stimme nicht und darf damit keine Befehle von dir entgegen nehmen.")
                        global_variables.voice_assistant.current_speaker = None
                    else:
                        if speaker:
                            logger.info("Sprecher ist {}", speaker)
                        global_variables.voice_assistant.current_speaker = speaker
                        global_variables.voice_assistant.current_speaker_fingerprint = recResult['spk']
                        sentence = recResult['text']
                        logger.info('Ich habe verstanden: "{}"', sentence)

                        output = global_variables.voice_assistant.intent_management.process(sentence, speaker)
                        logger.debug("Output: {}", output)
                        global_variables.voice_assistant.tts.say(output)
                        if self.show_balloon:
                            Notification.show("Interaktion", "Eingabe (" + speaker + "): " + sentence + ". Ausgabe: " + output, ttl=4000)

                        global_variables.voice_assistant.is_listening = False
                        global_variables.voice_assistant.current_speaker = None

            # Wird derzeit nicht zugehört?
            else:
                # Reaktiviere is_listening, wenn der Skill weitere Eingaben erforder
                if not global_variables.context is None:
                    # ... aber erst, wenn ausgeredet wurde
                    if not global_variables.voice_assistant.tts.is_busy():
                        global_variables.voice_assistant.is_listening = True
                else:
                    if not global_variables.voice_assistant.tts.is_busy():
                        self.app.icon.set_icon(constants.TRAY_ICON_IDLE, constants.TRAY_TOOLTIP + ": Bereit")

                    # Setze die Lautstärke auf Normalniveau zurück
                    global_variables.voice_assistant.audio_player.set_volume(global_variables.voice_assistant.volume)

                    # Prozessiere alle registrierten Callback Funktionen, die manche Intents
                    # jede Iteration benötigen
                    for cb in global_variables.voice_assistant.callbacks:
                        output = cb()
                        # Gibt die Callback Funktion einen Wert zurück? Dann versuche
                        # ihn zu sprechen.
                        if output:
                            if not global_variables.voice_assistant.tts.is_busy():
                                # Wird etwas abgespielt? Dann schalte die Lautstärke runter
                                if global_variables.voice_assistant.audio_player.is_playing():
                                    global_variables.voice_assistant.audio_player.set_volume(global_variables.voice_assistant.silenced_volume)
                                # Spreche das Ergebnis des Callbacks
                                global_variables.voice_assistant.tts.say(output)
                                if self.show_balloon:
                                    Notification.show('Callback', output, ttl=4000)

                                # Wir rufen die selbe Funktion erneut auf und geben mit,
                                # dass der zu behandelnde Eintrag abgearbeitet wurde.
                                # Im Falle der Reminder-Funktion wird dann z.B. der Datenbankeintrag
                                # für den Reminder gelöscht
                                cb(True)

                                # Zurücksetzen der Lautstärke auf Normalniveau
                                global_variables.voice_assistant.audio_player.set_volume(global_variables.voice_assistant.volume)

    def say_with_language(self, tts, lang_manager, key, **placeholders):
        """
        Dynamische TTS-Funktion, die eine übersetzte Nachricht spricht.

        :param tts: Text-to-Speech-Instanz
        :param lang_manager: LanguageManager-Instanz
        :param key: Schlüssel für die Nachricht in der Sprachdatei
        :param placeholders: Platzhalter, die in der Nachricht ersetzt werden
        """
        message = lang_manager.get(key, default="").format(**placeholders)
        tts.say(message)


def check_user_initialization():
    users_file_path = constants.find_data_file(os.path.join('users.json'))
    user_initialized = False

    if os.path.exists(users_file_path):
        try:
            with open(users_file_path, "r", encoding="utf-8") as f:
                users_data = json.load(f)
                if isinstance(users_data, dict) and "speakers" in users_data and len(users_data["speakers"]) > 0:
                    user_initialized = True
        except json.JSONDecodeError:
            user_initialized = False

    return user_initialized

def load_language_file(language):
    language_file = constants.find_data_file(os.path.join('languages', f'{language}.yml'))
    if not os.path.exists(language_file):
        logger.warning(f"Sprachdatei {language_file} nicht gefunden. Fallback auf Englisch.")
        language_file = constants.find_data_file(os.path.join('languages', 'en.yml'))

    with open(language_file, 'r', encoding='utf-8') as ymlfile:
        return yaml.safe_load(ymlfile)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.stdout = open('x.out', 'a')
    sys.stderr = open('x.err', 'a')
    multiprocessing.set_start_method('spawn')

    wx.Log.SetLogLevel(wx.LOG_Trace)

    global_variables.voice_assistant = VoiceAssistant()
    logger.info("Anwendung wurde gestartet")

    language_config = load_language_file(global_variables.voice_assistant.cfg['assistant']['language'])

    # Initialisierungsprüfung
    if not global_variables.voice_assistant.cfg['assistant']['user_initialized']:
        logger.info("Benutzer muss erstellt werden.")
        # Starte Benutzererstellung via process
        response = global_variables.voice_assistant.intent_management.process(language_config['intent']['start']['initial_user'], "sample_user")
        global_variables.voice_assistant.tts.say(response)
        while global_variables.voice_assistant.tts.is_busy():
            time.sleep(0.1)  # Vermeidet zu häufige Abfragen
        logger.info("TTS abgeschlossen. Weiter.")
    else:
        global_variables.voice_assistant.say_with_language(global_variables.voice_assistant.tts, global_variables.voice_assistant.lang_manager, "intent.start.welcome")
        while global_variables.voice_assistant.tts.is_busy():
            time.sleep(0.1)  # Vermeidet zu häufige Abfragen
        logger.info("TTS abgeschlossen. Weiter.")

    global_variables.voice_assistant.app.MainLoop()
