import os
import sys
from _msi import OpenDatabase, MSIDBOPEN_DIRECT, CreateRecord
from cx_Freeze import setup, Executable
sys.setrecursionlimit(5000)

includefiles = ['config.yml', 'empty.wav', 'idle.png', 'initializing.png', 'listening.png', 'speaking.png', 'download_icon.png', 'users.json', 'va.ico', 'intents/', 'languages/', 'MarianMTModel/', 'vosk_models/', 'user_databases/']

build_exe_options = {"packages": ["pyttsx3.drivers.sapi5", "pip", "idna", "geocoder", "text2numde", "fuzzywuzzy", "dateutil", "pyowm", "wikipedia", "pip._vendor.distlib", "pip._internal.commands.install", "pykeepass", "pynput", "pytz", "scipy", "words2num", "num2words", "comtypes", "winwifi"], "excludes": [], "include_files": includefiles}

base = "Win32GUI"


bdist_msi_options = {
        "add_to_path": True,
        "install_icon": "va.ico",
        "summary_data": {"author": "Rico Richter"},
        "upgrade_code": "{12345678-4321-1234-4321-123456789ABC}",
}

setup(  name = "Sprachassistent",
        version = "1.0",
        description = "Mein erster Sprachassistent",
        options = {
                "build_exe": build_exe_options,
                "bdist_msi": bdist_msi_options
        },
        executables = [Executable("main.py", base=base,icon="va.ico", shortcut_name="Sprachassistent",  shortcut_dir="DesktopFolder", uac_admin=True,)])


# Nachträgliches Bearbeiten der MSI-Datei
msi_path = os.path.join("dist", "Sprachassistent-1.0-win64.msi")
if os.path.exists(msi_path):
        print("MSI-Datei gefunden. Bearbeite Properties...")

        # MSI-Datenbank öffnen
        db = OpenDatabase(msi_path, MSIDBOPEN_DIRECT)

        # Füge ProgramMenuFolder hinzu
        cursor = db.OpenView("INSERT INTO Directory (Directory, Directory_Parent, DefaultDir) VALUES (?, ?, ?)")
        program_menu_record = CreateRecord(3)
        program_menu_record.SetString(1, "ProgramMenuFolder")  # Directory-Name
        program_menu_record.SetString(2, "TARGETDIR")         # Parent-Directory
        program_menu_record.SetString(3, ".")                # DefaultDir für Standardverzeichnis
        cursor.Execute(program_menu_record)

        # Zielverzeichnis für das Startmenü hinzufügen
        cursor = db.OpenView("INSERT INTO Directory (Directory, Directory_Parent, DefaultDir) VALUES (?, ?, ?)")
        start_menu_record = CreateRecord(3)
        start_menu_record.SetString(1, "StartMenuPrograms")  # Directory-Name
        start_menu_record.SetString(2, "ProgramMenuFolder")  # Parent-Directory
        start_menu_record.SetString(3, "Sprachassistent")    # Verzeichnisname im Startmenü
        cursor.Execute(start_menu_record)

        # Component für MAINCOMPONENT erstellen
        cursor = db.OpenView("INSERT INTO Component (Component, ComponentId, Directory_, Attributes) VALUES (?, ?, ?, ?)")
        component_record = CreateRecord(4)
        component_record.SetString(1, "MAINCOMPONENT")       # Name der Komponente
        component_record.SetString(2, "{12345678-4321-1234-4321-123456789ABC}")  # UUID der Komponente
        component_record.SetString(3, "TARGETDIR")           # Zielverzeichnis der Komponente
        component_record.SetInteger(4, 0)                    # Attribute (Standard: 0)
        cursor.Execute(component_record)

        # Verknüpfung von Feature und Component hinzufügen
        cursor = db.OpenView("INSERT INTO FeatureComponents (Feature_, Component_) VALUES (?, ?)")
        feature_component_record = CreateRecord(2)
        feature_component_record.SetString(1, "default")  # Existierendes Feature
        feature_component_record.SetString(2, "MAINCOMPONENT")  # Component, die Sie hinzugefügt haben
        cursor.Execute(feature_component_record)

        # Hersteller in die Property-Tabelle einfügen
        cursor = db.OpenView("SELECT * FROM Property WHERE Property = ?")
        record = CreateRecord(1)
        record.SetString(1, "Manufacturer")
        cursor.Execute(record)
        fetch = cursor.Fetch()
        if fetch:
                print("Hersteller gefunden, wird bearbeitet...")
                cursor = db.OpenView("UPDATE Property SET Value = ? WHERE Property = ?")
                update_record = CreateRecord(2)
                update_record.SetString(1, "Rico Richter")
                update_record.SetString(2, "Manufacturer")
                cursor.Execute(update_record)
        else:
                print("Hersteller nicht gefunden, wird hinzugefügt...")
                cursor = db.OpenView("INSERT INTO Property (Property, Value) VALUES (?, ?)")
                insert_record = CreateRecord(2)
                insert_record.SetString(1, "Manufacturer")
                insert_record.SetString(2, "Rico Richter")
                cursor.Execute(insert_record)

        # Shortcut für das Startmenü hinzufügen
        cursor = db.OpenView(
                "INSERT INTO Shortcut (Shortcut, Directory_, Name, Component_, Target, Arguments, Description, Icon_, WkDir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        shortcut_record = CreateRecord(9)  # 9 Felder notwendig, weil WkDir verwendet wird
        shortcut_record.SetString(1, "SprachassistentShortcut")  # Name des Shortcuts
        shortcut_record.SetString(2, "StartMenuPrograms")       # Zielverzeichnis im Startmenü
        shortcut_record.SetString(3, "Sprachassistent")         # Shortcut-Name
        shortcut_record.SetString(4, "MAINCOMPONENT")           # Name der Komponente
        shortcut_record.SetString(5, "[TARGETDIR]main.exe")     # Ziel des Shortcuts
        shortcut_record.SetString(6, "")                        # Keine Argumente
        shortcut_record.SetString(7, "Mein Sprachassistent")    # Beschreibung
        shortcut_record.SetString(8, "")                        # Icon des Shortcuts
        shortcut_record.SetString(9, "TARGETDIR")               # WkDir
        cursor.Execute(shortcut_record)

        # Änderungen speichern und schließen
        db.Commit()
        cursor.Close()
        db.Close()

        print("MSI-Properties erfolgreich bearbeitet.")
else:
        print(f"MSI-Datei nicht gefunden: {msi_path}")