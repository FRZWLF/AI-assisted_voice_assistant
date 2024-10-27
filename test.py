from audioplayer import AudioPlayer
import time

if __name__ == '__main__':

    ap = AudioPlayer()
    try:
        ap.set_volume(1)
        ap.play_stream("http://fritz.de/livemp3")
        time.sleep(5)
        ap.set_volume(0.1)
        ap.stop()
        ap.play_stream("http://fritz.de/livemp3")
        time.sleep(4)
        ap.stop()
    finally:
        if ap:
            ap.stop()