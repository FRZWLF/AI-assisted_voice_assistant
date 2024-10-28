import sys
import pvporcupine
from loguru import logger
import multiprocessing
from TTS import Voice
import yaml
import struct
import pyaudio
from vosk import Model, SpkModel, KaldiRecognizer
import json
import numpy as np
from usermgmt import UserMgmt
from intentmgmt import IntentManagement
from audioplayer import AudioPlayer
import wx.adv
import wx
import constants
import global_variables
from notification import Notification

#GUI-Anwendung mit pythonw main.py starten

CONFIG_FILE = "assistant_config.yml"


class TaskBarIcon(wx.adv.TaskBarIcon):

    def __init__(self,frame):
        self.frame = frame
        super(TaskBarIcon, self).__init__()
        self.set_icon(constants.TRAY_ICON_INITIALIZING, constants.TRAY_TOOLTIP + ": Initialisiere ...")

    def create_menu_item(self, menu, label, func):
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.Append(item)
        return item

    def CreatePopupMenu(self):
        menu = wx.Menu()
        self.create_menu_item(menu,'Beenden', self.on_exit)
        return menu

    def set_icon(self, path, tooltip=constants.TRAY_TOOLTIP):
        icon = wx.Icon(path)
        self.SetIcon(icon, tooltip)

    def on_exit(self, event):
        if global_variables.voice_assistant:
            global_variables.voice_assistant.terminate()
            wx.CallAfter(self.Destroy)
            self.frame.Close()

class MainApp(wx.App):
    def OnInit(self):
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        self.icon = TaskBarIcon(frame)
        self.Bind(wx.EVT_CLOSE, self.on_close_window)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update, self.timer)

        return True

    def update(self, event):
        if global_variables.voice_assistant:
            global_variables.voice_assistant.loop()

    def on_close_window(self, evt):
        self.icon.Destroy()
        evt.Skip()

class VoiceAssistant():

    def __init__(self):
        logger.info("Initialisiere VoiceAssistant...")

        self.app = MainApp(clearSigInt=False, redirect=True, filename='log.txt')

        logger.debug("Lese Konfiguration...")

        global CONFIG_FILE
        with open(CONFIG_FILE,'r',encoding="utf-8") as ymlfile:
            self.cfg = yaml.load(ymlfile,Loader=yaml.FullLoader)

        if self.cfg:
            logger.debug("Konfiguration erfolgreich gelesen.")
        else:
            logger.error("Konfiguration konnte nicht gelesen werden.")
            sys.exit(1)

        # Listen von Root-Objekten mit wiederum einer Liste von Objekten
        language = self.cfg['assistant']['language']
        if not language:
            language = "de"
        logger.info(f"Verwende Sprache {language}")

        self.show_balloon = self.cfg['assistant']['show_balloon']

        logger.debug("Initialisiere Wake Word Erkennung...")
        self.wake_words = self.cfg["assistant"]["wakewords"]
        if not self.wake_words:
            self.wake_words = ['jarvis']
        logger.debug("Wake Words sind {}" ','.join(self.wake_words))
        self.porcupine = pvporcupine.create(keywords=self.wake_words, sensitivities=[0.6, 0.6])
        logger.info("Wake Words Erkennung wurde initialisiert.")

        #Audio-Stream needed
        logger.info("Initialisiere Audioeingabe...")
        self.pa = pyaudio.PyAudio()

        #show devices
        for i in range(self.pa.get_device_count()):
            logger.debug("id: {},name: {}", self.pa.get_device_info_by_index(i).get('index'), self.pa.get_device_info_by_index(i).get('name'))

        #selecting mic
        self.audio_stream = self.pa.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self.porcupine.frame_length,
            input_device_index=1
        )
        logger.info("Audiostream geöffnet...")

        # Lese Lautstärke
        self.volume = self.cfg["assistant"]["volume"]
        self.silenced_volume = self.cfg["assistant"]["silenced_volume"]

        logger.info("Voice Assistant wird initialisiert...")
        self.tts = Voice()

        voices = self.tts.get_voice_keys_by_language(language)
        if len(voices) > 0:
            self.tts.set_voice(voices[0])
            logger.info(f"Stimme {voices[0]}")
        else:
            logger.warning("Es wurde keine Stimme gefunden.")
        self.tts.set_volume(self.volume)
        self.tts.say("Sprachausgabe aktiviert.")
        if self.show_balloon:
            Notification.show('Initialisierung', 'Sprachausgabe aktiviert', ttl=4000)
        logger.debug("Voice Assistant initialisiert")

        logger.info("Initialisiere Spracherkennung...")
        s2t_model = Model('./vosk-model-de-0.21')
        speaker_model = SpkModel('./vosk-model-spk-0.4')
        self.rec = KaldiRecognizer(s2t_model, 16000, speaker_model)
        self.is_listening = False
        logger.info("Spracherkennung initialisiert.")


        logger.info("Initialisiere Benutzerverwaltung...")
        self.user_management = UserMgmt(init_dummies=True)
        self.allow_only_known_speakers = self.cfg['assistant']['allow_only_known_speakers']
        logger.info("Benutzerverwaltung initialisiert.")

        # Initialisiere den Audio-Player
        # mixer.init()
        # mixer.music.set_volume(self.volume)
        self.audio_player = AudioPlayer()
        self.audio_player.set_volume(self.volume)

        logger.info("Initialisiere Intent Management...")
        self.intent_management = IntentManagement()
        logger.info("{} Intents gefunden.", self.intent_management.get_count())
        logger.info("Intent Management wurde aus initialisiert.")

        # Erzeuge eine Liste, die die Callback Funktionen vorhält
        self.callbacks = self.intent_management.register_callbacks()
        logger.info('{} callbacks gefunden', len(self.callbacks))
        self.tts.say("Initialisierung abgeschlossen")
        if self.show_balloon:
            Notification.show('Initialisierung', 'Abgeschlossen', ttl=4000)


        self.app.icon.set_icon(constants.TRAY_ICON_IDLE, constants.TRAY_TOOLTIP + ": Bereit")
        timer_start_res = self.app.timer.Start(milliseconds=1, oneShot=wx.TIMER_CONTINUOUS)
        logger.debug("Timer gestartet? {}", timer_start_res)


        self.tts.say("Initialisierung abgeschlossen.")

    def __detectSpeaker__(self, input):
        bestSpeaker = None
        bestCosDist = 100
        for speaker in self.user_management.speaker_table.all():
            nx = np.array(speaker.get('voice'))
            ny = np.array(input)
            cosDist = 1-np.dot(nx, ny) / np.linalg.norm(nx) / np.linalg.norm(ny)
            if cosDist < bestCosDist:
                if cosDist < 0.3:
                    bestCosDist = cosDist
                    bestSpeaker = speaker.get('name')
        return bestSpeaker

    def terminate(self):
        logger.debug("Beginne Aufräumarbeiten...")

        # Stoppe den Timer
        self.app.timer.Stop()

        # Speichern der Konfiguration
        global_variables.voice_assistant.cfg["assistant"]["volume"] = global_variables.voice_assistant.volume
        global_variables.voice_assistant.cfg["assistant"]["silenced_volume"] = global_variables.voice_assistant.silenced_volume
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
            pcm_unpacked = struct.unpack_from("h" * global_variables.voice_assistant.porcupine.frame_length,pcm)
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
                    logger.info("recResult {}", recResult)
                    speaker = global_variables.voice_assistant.__detectSpeaker__(recResult['spk'])

                    if (speaker is None) and (global_variables.voice_assistant.allow_only_known_speakers == True):
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
                                    global_variables.voice_assistant.audio_player.set_volume(global_variables.voice_assistant.audio_player.set_volume(global_variables.voice_assistant.silenced_volume))
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
                                global_variables.voice_assistant.audio_player.music.set_volume(global_variables.voice_assistant.volume)


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn')
    global_variables.voice_assistant = VoiceAssistant()
    logger.info("Anwendung wurde gestartet")
    global_variables.voice_assistant.app.MainLoop()