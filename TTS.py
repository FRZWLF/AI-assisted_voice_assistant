import time
import pyttsx3
import multiprocessing
import global_variables
import constants


def __speak__(text, voiceId, volume):
    if global_variables.voice_assistant:
        global_variables.voice_assistant.app.icon.set_icon(constants.TRAY_ICON_SPEAKING, constants.TRAY_TOOLTIP + ": " + text)
    engine = pyttsx3.init()
    engine.setProperty('voice', voiceId)
    engine.setProperty('volume', volume)
    engine.say(text)
    engine.runAndWait()


class Voice:

    def __init__(self):
        self.process = None
        self.voiceId = "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_DE-DE_HEDDA_11.0"
        self.volume = 0.5

    def say(self, text):
        if self.process:
            self.stop()
        p = multiprocessing.Process(target=__speak__, args=(text, self.voiceId, self.volume))
        p.start()
        self.process = p

    def set_voice(self, voiceId):
        self.voiceId = voiceId

    def stop(self):
        if self.process:
            self.process.terminate()

    # Setze die Lautstärke mit der gesprochen wird
    def set_volume(self, volume=0.5):
        self.volume = volume

    def is_busy(self):
        if self.process:
            return self.process.is_alive()

    def get_voice_keys_by_language(self, language=''):
        result = []
        engine = pyttsx3.init()
        lang_search_string = language.upper() + "-"
        voices = engine.getProperty('voices')
        for voice in voices:
            if language == '':
                result.append(voice.id)
            elif lang_search_string in voice.id:
                result.append(voice.id)
        return result
