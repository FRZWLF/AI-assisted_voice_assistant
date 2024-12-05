import threading
import time

from loguru import logger
import ffmpeg
import sounddevice as sd
import soundfile as sf
import multiprocessing
import queue
import numpy as np

import global_variables


class AudioPlayer:

    def __init__(self):
        self._process = None
        self._volume = multiprocessing.Value('d', 0.5)  #Value als gemeinsamer Speicher für Prozesse, um Lautstärke eines laufenden Streams ändern zu können
        self._q = None
        self._producer_running = False

    def play_file(self, file):
        if self._process:
            self.stop()
        self._process = multiprocessing.Process(target=self._play_file, args=(file,))
        self._process.start()

    def play_stream(self, source):
        # Setze Lautstärke vor dem Starten des Streams auf die Standardlautstärke
        #logger.debug("Setze Lautstärke vor Streamstart auf: {}", global_variables.voice_assistant.volume)
        self.set_volume(global_variables.voice_assistant.volume)
        if self._process:
            self.stop()
        self._process = multiprocessing.Process(target=self._play_stream, args=(source, ))
        self._process.start()

    def _play_file(self, file):
        sd.default.reset()
        data, fs = sf.read(file, dtype='float32')
        sd.play(data * self._volume.value, fs, device=sd.default.device['output'])
        status = sd.wait()
        if status:
            logger.error("Fehler bei der Soundwiedergabe {}.", status)

    def _play_stream(self, source):
        sd.default.reset()
        self._q = queue.Queue(maxsize=100)
        logger.info("Spiele auf Device {}.", sd.default.device['output'])

        def producer_thread(process, q, channels, read_size):
            """
            Liest Daten aus dem ffmpeg-Prozess und schreibt sie in die Queue.
            """
            try:
                while self._producer_running:
                    data = np.frombuffer(process.stdout.read(read_size), dtype='float32')
                    if len(data) == 0:
                        break
                    data.shape = -1, channels
                    q.put(data, timeout=None)
            except Exception as e:
                logger.error(f"Fehler im Producer-Thread: {e}")

        def _callback_stream(outdata, frames, time, status):
            if status.output_underflow:
                raise sd.CallbackAbort
            assert not status

            try:
                data = self._q.get_nowait()
                # Dynamische Anwendung der Lautstärke
                with self._volume.get_lock():
                    adjusted_volume = self._volume.value
                data = data * adjusted_volume
                assert len(data) == len(outdata)
                outdata[:] = data
                #logger.debug("Angewendete Lautstärke im Callback: {}", adjusted_volume)
            except queue.Empty as e:
                #logger.warning("Queue ist leer, sende Stille.")
                outdata.fill(0)
                #raise sd.CallbackAbort from e

        try:
            info = ffmpeg.probe(source)
        except ffmpeg.Error as e:
            logger.error(e)

        streams = info.get('streams', [])
        if len(streams) != 1:
            logger.error('Es darf nur genau ein Stream eingegeben werden.')

        stream = streams[0]

        if stream.get('codec_type') != 'audio':
            logger.error("Stream muss ein Audio Stream sein")

        channels = stream['channels']
        samplerate = float(stream['sample_rate'])

        logger.debug("Stream-Kanäle: {}, Sample-Rate: {}, Lautstärke: {}", channels, samplerate, self._volume)

        print(channels)
        print(samplerate)

        try:
            #USE for dynamic volume change rather than static by filtering
            process = ffmpeg.input(source).output('pipe:', format='f32le', acodec='pcm_f32le', ac=channels, ar=samplerate, loglevel='quiet').run_async(pipe_stdout=True)
            #process = ffmpeg.input(source).filter('volume', self._volume).output('pipe:', format='f32le', acodec='pcm_f32le', ac=channels, ar=samplerate, loglevel='quiet').run_async(pipe_stdout=True)

            # Starte den Producer-Thread
            self._producer_running = True
            producer = threading.Thread(target=producer_thread, args=(process, self._q, channels, 1024 * channels * 4))
            producer.daemon = True
            producer.start()

            #stream = sd.RawOutputStream(samplerate=samplerate, blocksize=1024, device=sd.default.device['output'], channels=channels, dtype='float32', callback=_callback_stream)
            stream = sd.OutputStream(samplerate=samplerate, blocksize=1024, device=sd.default.device['output'], channels=channels, dtype='float32', callback=_callback_stream)

            with stream:
                while self._producer_running:
                    time.sleep(0.1)
        except Exception as e:
            logger.error(f"Fehler während der Wiedergabe: {e}")
        finally:
            self._producer_running = False

    def stop(self):
        if self._process:
            logger.debug("Stoppe derzeitige Wiedergabe.")
            self._producer_running = False
            self._process.terminate()
            self._process.join()

    def is_playing(self):
        if self._process:
            return self._process.is_alive()

    def set_volume(self, volume):
        with self._volume.get_lock():  # Sperrt den Zugriff für andere Prozesse
            self._volume.value = max(0.0, min(volume, 1.0))
        #logger.debug("Lautstärke wurde geändert auf: {}", self._volume.value)

    def get_volume(self):
        with self._volume.get_lock():
            return self._volume.value

