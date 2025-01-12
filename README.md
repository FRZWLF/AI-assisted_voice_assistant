# AI-Assisted Voice Assistant

Ein einfacher KI-unterstützter Sprachassistent, der per Mikrofon gesteuert werden kann. Der Sprachassistent funktioniert ohne Anbindung an Cloud Dienste und kann als ausführbare Datei (.exe) heruntergeladen und gestartet werden.

---

## Inhaltsverzeichnis
1. [Über das Projekt](#%C3%BCber-das-projekt)
2. [Features](#features)
3. [Technologie-Stack](#technologie-stack)
4. [Voraussetzungen](#voraussetzungen)
5. [Installation](#installation)
6. [Verwendung](#verwendung)
7. [TO-DO](#zuk%C3%BCnftige-pl%C3%A4ne)
8. [Lizenz](#lizenz)

---

## Über das Projekt
Dieses Projekt ist ein einfacher KI-unterstützter Sprachassistent, der im Rahmen des Udemy-Kurses ["Entwicklung eines KI-gestützten Sprachassistenten mit Python"](https://www.udemy.com/course/ki-sprachassistent/) als Code Along Projekt entwickelt wurde. Ein Großteil des Codes entspricht dem Repository [AISpeechAssistant](https://github.com/padmalcom/AISpeechAssistant) von [padmalcom](https://github.com/padmalcom). Aufgrund von Problemen mit Snips NLU wurde auf eine NLU-Integration verzichtet. Stattdessen wurde weiterhin mit chatbot-ai gearbeitet, wodurch nicht alle Szenarien z.B. bei dem intent reminder abgedeckt werden konnten. In eigenem Interesse wurde der Chatbot um einige Features erweitert. 

### WICHTIG!!! 

Es handelt sich um mein erstes Python Projekt. Es wurde versucht den Python Style Guide zu befolgen. Aufgrund diverser Probleme bei der Integration von Snips NLU, wird dieses Projekt nicht weiter verfolgt. 

Stattdessen wird der Voice Assistant mit Rasa NLU neu augesetzt (work in progress): [NLU_voice_assistant](https://github.com/FRZWLF/NLU_voice_assistant)

---

## Features
- **Multilingualität**:
  - Intents und Ausgabe unterstützen Deutsch, Englisch, Französisch, Spanisch, Italienisch, Japanisch und Russisch.
  - Verwendung von MarianMTModels für Übersetzungen.
- **Downloader**: Automatischer Download der benötigten Vosk- und MarianMT-Modelle.
- **Mikrofon-Erkennung**: Automatische Erkennung des Standard-Mikrofons.
- **Unterstützte Intents**:
  - Animalsounds
  - Sprachenwechsel
  - Radiostream
  - Uhrzeit
  - Standordabfrage
  - Password-Datenbank
  - Fragespiel
  - Reminder und Timer
  - Smarthomeintegration für Shelly-Geräte
  - User-Management
  - Lautstärkenmanagement
  - Wetterabfrage
  - Wiki-Abfrage
- **Capture Voice Sample**: Anlage neuer Nutzer und deren Stimmen mithilfe von Voiceencoder.
- **Ausführbare Datei**: Kann direkt als .exe-Datei gestartet werden.

---

## Technologie-Stack
### Programmiersprache
- **Python**
### Bibliotheken und Module
- **Spracherkennung**:
  - Vosk: Sprachmodelle zur Erkennung von Sprachbefehlen
  - pvporcupine: Wake Word Detection
  - Sounddevice: Mikrofonsteuerung
- **Text-to-Speech (TTS)**:
  - Pyttsx3: Text-zu-Sprache-Konvertierung
- **Übersetzungen**:
  - MarianMTModels: Multilinguale Übersetzung
- **Datenbank**:
  - TinyDB: Lokale Speicherung
- **Location Services**:
  - Geocoder: Standortabfragen
- **Audio**:
  - FFMPEG: Verarbeitung von Audiostreams
- **Passwortmanagement**:
  - PyKeePass: Verwaltung eines Passwortdepots
- **Wetterabfragen**:
  - PyOWM: Zugriff auf Wetterdaten
- **Wissensdatenbank**:
  - Wikipedia: Abfragen von Wikipedia-Artikeln
- **Voice Management**:
  - Voiceencoder: Erstellung von Sprachprofilen

### Entwicklungswerkzeuge
- **IntelliJ IDEA**: IDE zur Entwicklung und Verwaltung des Projekts
- **Conda**: Verwaltung der virtuellen Umgebung und Abhängigkeiten

---

## Voraussetzungen
Für die Nutzung der Anwendung:
- Keine zusätzlichen Abhängigkeiten erforderlich
- Download und Ausführung der `.msi`-Datei
- Mikrofon und Lautsprecher für Sprachsteuerung

Für Entwickler, die das Projekt klonen und bearbeiten möchten:
- Python 3.10
- Installierter Paketmanager (pip oder Conda)
- Mikrofon und Lautsprecher
- Alle Abhängigkeiten sind in der `requirements.txt` definiert

---

## Installation
1. **Repository klonen**:
   ```bash
   git clone https://github.com/FRZWLF/AI-assisted_voice_assistant.git
   cd AI-assisted_voice_assistant
   ```
2. **Virtuelle Umgebung erstellen und aktivieren**:
   ```bash
   conda create -n voice_assistant python=3.8
   conda activate voice_assistant
   ```
3. **Abhängigkeiten installieren**:
   ```bash
   pip install -r requirements.txt
   ```

---

## Verwendung
1. **Starten des Sprachassistenten**:
   ```bash
   python main.py
   ```
   Oder starte die `.msi`-Datei direkt.
2. **Für Sprachbefehle**: Aktiviere das Mikrofon und sprich das Wake Word **bumblebee** oder **americano**.

---

## TO-DO
- **Smarthome-Geräte**: Unterstützung für weitere Smarthome-Geräte neben Shelly.
- **Downloader verbessern**: Fortschrittsanzeige für den Modell-Download integrieren.
- **NLU-Integration**: NLU wieder hinzufügen und stabilisieren.
- **Antworten erweitern**: Bei nicht erkannten Intents GPT-2 verwenden, um Antworten zu generieren.
- **Raspberry Pi Portierung**: Das Projekt auf Raspberry Pi lauffähig machen.
- **Verbindungsstatus anzeigen**: Online-Abhängigkeiten (z. B. durch eine LED oder ein Popup) markieren.
- **Multi-Assistant-Cluster**: Assistants für mehrere Räume verknüpfen und synchronisieren.
- **Interaktivität erhöhen**: Konversationsinitiation durch den Assistenten, z. B. mit Fragen wie "Wie war dein Tag?" oder "Hat dir das Wetter gefallen, das du gestern angefragt hast?".

---

## Lizenz
Dieses Projekt steht unter der MIT-Lizenz. Details findest du in der Datei `LICENSE`.

