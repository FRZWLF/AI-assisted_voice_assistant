import sys
from loguru import logger
import multiprocessing

from vosk.transcriber.transcriber import SAMPLE_RATE

from TTS import Voice
import yaml
import struct
import pyaudio
import os

from vosk import Model, SpkModel, KaldiRecognizer
import json
import text2numde

CONFIG_FILE = "config.yml"
FRAME_LENGTH = 512
SAMPLE_RATE = 16000

class VoiceAssistant():

    def __init__(self):

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


        #Audio-Stream needed
        logger.info("Initialisiere Audioeingabe...")
        self.pa = pyaudio.PyAudio()

        #show devices
        for i in range(self.pa.get_device_count()):
            logger.debug("id: {},name: {}", self.pa.get_device_info_by_index(i).get('index'), self.pa.get_device_info_by_index(i).get('name'))

        #selecting mic
        self.audio_stream = self.pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=FRAME_LENGTH,
            input_device_index=1
        )

        logger.info("Audiostream geöffnet...")

        logger.info("Voice Assistant wird initialisiert...")
        self.tts = Voice()

        voices = self.tts.get_voice_keys_by_language(language)
        if len(voices) > 0:
            self.tts.set_voice(voices[0])
            logger.info(f"Stimme {voices[0]}")
        else:
            logger.warning("Es wurde keine Stimme gefunden.")

        logger.info("Initialisiere Spracherkennung...")
        s2t_model = Model('./vosk-model-de-0.21')
        speaker_model = SpkModel('./vosk-model-spk-0.4')
        self.rec = KaldiRecognizer(s2t_model, 16000, speaker_model)


        logger.info("Spracherkennung initialisiert.")

        self.tts.say("Initialisierung abgeschlossen.")

    def run(self):
        logger.info("Voice Assistant wird gestartet...")

        try:
            while True:

                pcm = self.audio_stream.read(FRAME_LENGTH)


                if self.rec.AcceptWaveform(pcm):
                    recResult = json.loads(self.rec.Result())
                    sentence = recResult['text']
                    logger.info('Ich habe verstanden: "{}"', sentence)

                    if sentence.lower().startswith('kevin'):
                        sentence = sentence[5:]
                        sentence = sentence.strip()
                        logger.info("Verarbeite Befehl {}.", sentence)

        except KeyboardInterrupt:
            logger.info("Per Keyboard beendet.")
        finally:
            logger.debug("Beginne Aufräumarbeiten...")

            if self.audio_stream:
                self.audio_stream.close()

            if self.pa is not None:
                self.pa.terminate()


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn')

    va = VoiceAssistant()
    va.run()