import sys
import os

def find_data_file(filename):
    if getattr(sys, "frozen", False):
        datadir = os.path.dirname(sys.executable)
    else:
        datadir = os.path.dirname(__file__)
    return os.path.join(datadir, filename)

# Konstanten für die Darstellung des Icons
TRAY_TOOLTIP = 'Voice Assistant'
TRAY_ICON_INITIALIZING = find_data_file('initializing.png')
TRAY_ICON_IDLE = find_data_file('idle.png')
TRAY_ICON_LISTENING = find_data_file('listening.png')
TRAY_ICON_SPEAKING = find_data_file('speaking.png')
TRAY_ICON_DOWNLOADING = find_data_file('download_icon.png')