import ipaddress
import random
import socket
import subprocess
import time
from multiprocessing.pool import ThreadPool
from loguru import logger
from chatbot import register_call
from tinydb import TinyDB, Query
import winwifi
import constants
import global_variables
import os
import yaml
import requests
from words2num import w2n
from marianMTModels import Translator


# Lade die Config global
CONFIG_PATH = constants.find_data_file(os.path.join('intents', 'functions', 'smarthome', 'config_smarthome.yml'))
DEVICES_DB_PATH = constants.find_data_file(os.path.join('intents', 'functions', 'smarthome', 'smartdevices_db.json'))
db = TinyDB(DEVICES_DB_PATH)
devices_table = db.table('devices')


def __read_config__():
    cfg = None

    LANGUAGE = global_variables.voice_assistant.cfg['assistant']['language']

    with open(CONFIG_PATH, "r", encoding='utf8') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    return cfg, LANGUAGE


def discover_lan_devices():
    """
    Führt einen Ping-Scan durch, um Geräte im lokalen Netzwerk zu finden.
    """
    logger.debug("Starte LAN-Gerätesuche...")
    try:
        logger.info("Starte LAN-Scan...")
        local_ip = socket.gethostbyname(socket.gethostname())
        ip_network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)

        # Pingen einer einzelnen IP-Adresse
        def ping(ip):
            try:
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "1000", ip],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                res = result.stdout.decode("utf-8", errors="ignore")
                # logger.debug(f"Pinge IP {ip}: {'Erreichbar' if res == 0 else 'Nicht erreichbar'}")
                return ip if "Antwort von" in str(res) else None
            except Exception:
                return None

        pool = ThreadPool(10)
        active_ips = pool.map(ping, [str(ip) for ip in ip_network])
        pool.close()
        pool.join()

        # Filtere die gefundenen Geräte
        local_devices = [{"ip": ip} for ip in filter(None, active_ips)]
        logger.info(f"Gefundene Geräte im LAN: {local_devices}")

        return local_devices

    except Exception as e:
        print(f"Fehler bei der LAN-Gerätesuche: {e}")
        return []


def discover_shelly_via_wlan():
    """
    Sucht nach Shelly-Geräten in der WLAN-Netzwerkliste.
    """
    try:
        logger.info("Starte WLAN-Scan mit WinWiFi...")
        # Führt einen WLAN-Scan aus
        winwifi.WinWiFi.scan()
        time.sleep(10)
        logger.info("WLAN-Refresh mit WinWiFi erfolgreich.")
        return True
    except Exception as winwifi_error:
        logger.warning(f"WinWiFi-Scan fehlgeschlagen: {winwifi_error}")

    try:
        print("Starte WLAN-Scan...")
        result = subprocess.run(
            ["netsh", "wlan", "show", "network"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Dekodiere mit explizitem Fehler-Handling
        networks = result.stdout.decode("utf-8", errors="ignore")

        # Suche nach Netzwerken, die "Shelly" enthalten
        shelly_networks = []
        for line in networks.split("\n"):
            if "shelly" in line.lower():
                ssid = line.split(":")[1].strip() if ":" in line else line.strip()
                shelly_networks.append({"device": ssid, "ip": "192.168.33.1", "type": "WiFi"})


        if shelly_networks:
            logger.info(f"Gefundene Shelly-Access-Points: {shelly_networks}")
        else:
            logger.warning("Keine Shelly-Access-Points gefunden.")
        return shelly_networks

    except Exception as e:
        print(f"Fehler beim WLAN-Scan: {e}")
        return []


def discover_shelly_device():
    """
    Sucht nach Shelly-Geräten: Zuerst über WLAN-Access-Point, dann über LAN im Heim-WLAN.
    """
    # Schritt 1: Suche nach Shelly-SSIDs (Access-Point-Modus)
    shelly_devices_via_wlan = discover_shelly_via_wlan()
    if shelly_devices_via_wlan:
        logger.info(f"Gefundene Shelly-Geräte über WLAN: {shelly_devices_via_wlan}")
        return shelly_devices_via_wlan

    # Keine Geräte gefunden
    logger.warning("Keine Shelly-Geräte im WLAN gefunden.")
    return []

def is_shelly_device(ip):
    """
    Prüft, ob ein Gerät mit der gegebenen IP-Adresse ein Shelly-Gerät ist.
    """
    try:
        response = requests.get(f"http://{ip}/rpc/Shelly.GetDeviceInfo", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "shelly" in data.get("id", "").lower():
                logger.info(f"Shelly-Gerät gefunden: {data}")
                return True
    except Exception:
        pass
    return False


def device_already_exists(device_id):
    Device = Query()
    return devices_table.contains((Device.id == device_id))


def get_current_ssid():
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = str(result.stdout.decode("utf-8", errors="ignore"))
        logger.info(f"Netsh-Output:\n{output}")
        for line in output.split("\n"):
            if "SSID" in line and "BSSID" not in line:  # Vermeide "BSSID"
                logger.info(f"Gefundene SSID-Zeile: {line.strip()}")
                return line.split(":")[1].strip()
        logger.warning("SSID konnte nicht gefunden werden.")
        return None
    except Exception as e:
        print(f"Fehler beim Auslesen der SSID: {e}")
        return None


def get_wifi_password(ssid):
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profile", ssid, "key=clear"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = str(result.stdout.decode("utf-8", errors="ignore"))
        logger.info(f"Netsh-Output:\n{output}")

        # Suche nach "Schlüsselinhalt" in der Ausgabe
        for line in output.split("\n"):
            if "Schlsselinhalt" in line:  # Deutsch: Schlüsselinhalt statt Key Content
                password = line.split(":")[1].strip()
                logger.info(f"Passwort für SSID '{ssid}': {password}")
                return password

        logger.warning(f"Kein Passwort für SSID '{ssid}' gefunden.")

        return None
    except Exception as e:
        logger.error(f"Fehler beim Auslesen des Passworts für SSID '{ssid}': {e}")
        return None


def configure_shelly_network(shelly_ip, ssid, password):
    try:
        response = requests.get(f"http://{shelly_ip}/rpc/Shelly.GetDeviceInfo", timeout=15)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Gerät nicht erreichbar: {e}")

    try:
        url = f"http://{shelly_ip}/rpc/WiFi.SetConfig"
        headers = {
            "Content-Type": "application/json"
        }
        payload = {
            "config": {
                "sta": {
                    "ssid": ssid,
                    "pass": password,
                    "enable": True
                }
            }
        }
        logger.info(f"Sende Netzwerk-Konfigurationsdaten an {url}...")
        logger.info(f"Payload: {payload}")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"HTTP-Status: {response.status_code}")
        logger.info(f"Response-Body: {response.text}")
        if response.status_code != 200:
            logger.error(f"Fehler bei der Netzwerkverbindung: {response.text}")
            return False

        logger.info("WiFi-Konfiguration erfolgreich gesendet. Überprüfe Verbindung...")

        # Validierung der Verbindung
        if not validate_shelly_wifi_connection(shelly_ip):
            logger.error("Die Verbindung konnte nicht hergestellt werden.")
            return False

        logger.info("Shelly-Gerät erfolgreich mit dem Heim-WLAN verbunden.")
        return True

    except Exception as e:
        logger.error(f"Fehler beim Verbinden des Geräts: {e}")
        return False


def validate_shelly_wifi_connection(shelly_ip, retries=5, delay=5):
    """
    Validiert, ob das Shelly-Gerät erfolgreich mit dem Heim-WLAN verbunden wurde.
    """
    status_url = f"http://{shelly_ip}/rpc/WiFi.GetStatus"
    for attempt in range(retries):
        logger.info(f"Versuche, den WiFi-Status von {shelly_ip} abzufragen (Versuch {attempt + 1}/{retries})...")
        try:
            response = requests.get(status_url, timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                logger.info(f"WiFi-Status: {status_data}")

                # Erfolgreich verbunden?
                if status_data.get("sta_ip") and status_data["sta_ip"] != "0.0.0.0":
                    logger.info(f"Shelly ist verbunden. IP-Adresse: {status_data['sta_ip']}")
                    return True
                elif status_data["status"] == "disconnected":
                    logger.warning("Gerät ist noch nicht verbunden. Warte auf Verbindung...")

        except Exception as e:
            logger.error(f"Fehler bei der Anfrage: {e}")

        time.sleep(delay)

    logger.error("Keine erfolgreiche Verbindung nach mehreren Versuchen.")
    return False


def find_shelly_ip_in_lan():
    devices = discover_lan_devices()
    logger.info(f"Gefundene LAN-Geräte: {devices}")
    for device in devices:
        try:
            response = requests.get(f"http://{device['ip']}/rpc/Shelly.GetDeviceInfo", timeout=15)
            if response.status_code == 200:
                data = response.json()
                if "shelly" in data.get("id", "").lower():
                    shelly_info = {
                        "ip": device["ip"],
                        "id": data.get("id"),
                        "name": data.get("name", "Shelly")
                    }
                    logger.info(f"Shelly-Gerät gefunden: {shelly_info}")
                    return shelly_info
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen von Shelly-Informationen von {device['ip']}: {e}")
            continue
    return None


def create_wifi_profile(ssid):
    try:
        # Temporäre XML-Datei für das WLAN-Profil erstellen
        profile_content = f"""
        <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
            <name>{ssid}</name>
            <SSIDConfig>
                <SSID>
                    <name>{ssid}</name>
                </SSID>
            </SSIDConfig>
            <connectionType>ESS</connectionType>
            <connectionMode>manual</connectionMode>
            <MSM>
                <security>
                    <authEncryption>
                        <authentication>open</authentication>
                        <encryption>none</encryption>
                        <useOneX>false</useOneX>
                    </authEncryption>
                </security>
            </MSM>
        </WLANProfile>
        """
        profile_path = f"{ssid}.xml"
        with open(profile_path, "w") as profile_file:
            profile_file.write(profile_content)

        # Profil importieren
        result = subprocess.run(
            ["netsh", "wlan", "add", "profile", f"filename={profile_path}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode == 0:
            logger.info(f"WLAN-Profil für '{ssid}' erfolgreich erstellt.")
            return True
        else:
            logger.error(f"Fehler beim Erstellen des WLAN-Profils: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des WLAN-Profils: {e}")
        return False



def connect_to_shelly_ap(ssid):
    """
    Verbindet den PC mit dem Shelly-Access-Point.
    """
    try:
        logger.info(f"Versuche Verbindung zu '{ssid}'...")
        subprocess.run(["netsh", "wlan", "connect", f"name={ssid}"], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info(f"Mit dem Shelly-Access-Point '{ssid}' verbunden.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Fehler beim Verbinden mit dem Access-Point '{ssid}': {e}")
        return False


def reconnect_to_home_wifi(ssid):
    """
    Verbindet den PC zurück mit dem Heim-WLAN.
    """
    try:
        subprocess.run(["netsh", "wlan", "connect", "name=" + ssid], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info(f"Zurück mit Heim-WLAN '{ssid}' verbunden.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Fehler beim Zurückverbinden mit '{ssid}': {e}")
        return False


@register_call("add_smart_device")
def add_smart_device(session_id="general", dummy=0):
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_smartdevice_state", None)
    if session_state is None:
        session_state = global_variables.new_smartdevice_state = {
            "step": 0,
            "devices": [],
            "selected_device": None,
        }

    if session_state["step"] == 0:
        global_variables.voice_assistant.is_listening = False
        logger.info("Starte Gerätesuche...")

        devices = discover_shelly_device()
        if not devices:
            global_variables.new_smartdevice_state = None
            global_variables.context = None
            return cfg['intent']['smarthome'][language]['no_devices']

        # Geräte speichern und nummerieren
        session_state["devices"] = devices
        response = []
        for index, device in enumerate(devices, 1):
            response.append(f"{index}. {device['device']} (IP: {device['ip']})")
        device_list = "\n".join(response)

        session_state["step"] += 1
        global_variables.context = select_smart_device
        return random.choice(cfg['intent']['smarthome'][language]['found_devices']).format(device_list)


def select_smart_device(selection=None):
    if not global_variables.voice_assistant.is_listening:
        global_variables.voice_assistant.is_listening = True
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_smartdevice_state", None)

    marian = Translator(language, 'en')
    selection = marian.translate([selection.strip()])[0].lower()
    try:
        selection = w2n(selection)
    except Exception as e:
        logger.error(f"Fehler bei der Zahlenerkennung: {e}")
        return cfg['intent']['smarthome'][language]['selection_error']

    if not session_state:
        return cfg['intent']['smarthome'][language]['no_session']

    if session_state["step"] == 1:
        global_variables.voice_assistant.is_listening = False
        if not selection:
            return cfg['intent']['smarthome'][language]['no_selection']

        # Validierung der Auswahl
        try:
            selection_index = int(selection) - 1
            devices = session_state["devices"]
            if selection_index < 0 or selection_index >= len(devices):
                return random.choice(cfg['intent']['smarthome'][language]['out_of_len']).format(len(devices))
        except ValueError:
            return cfg['intent']['smarthome'][language]['value_error']

        selected_device = session_state["devices"][selection_index]
        session_state["selected_device"] = selected_device

        # Schritt: Gerät mit Netzwerk verbinden
        if selected_device["ip"] == "192.168.33.1":  # Gerät im Access-Point-Modus
            logger.info("Verbinde Shelly-Gerät mit dem Netzwerk...")

            ssid = get_current_ssid()
            password = get_wifi_password(ssid)
            if not ssid or not password:
                global_variables.new_smartdevice_state = None
                global_variables.context = None
                return cfg['intent']['smarthome'][language]['no_home_wifi_data']

            # Mit Shelly-Access-Point verbinden
            if not connect_to_shelly_ap(selected_device["device"]):
                # Profil erstellen und erneut versuchen
                if not create_wifi_profile(selected_device["device"]) or not connect_to_shelly_ap(selected_device["device"]):
                    global_variables.new_smartdevice_state = None
                    global_variables.context = None
                    return cfg['intent']['smarthome'][language]['shelly_connection_failed']

            logger.info(f"Erfolgreich mit Shelly-Access-Point '{selected_device['device']}' verbunden.")

            # Heim-WLAN-Daten an Shelly senden
            if not configure_shelly_network(selected_device["ip"], ssid, password):
                logger.info("Prüfe, ob die Verbindung zum Heim-WLAN erfolgreich war...")
                global_variables.new_smartdevice_state = None
                global_variables.context = None
                return cfg['intent']['smarthome'][language]['home_wifi_connection_failed']

            logger.info("Warte 30 Sekunden, damit das Shelly-Gerät sich mit dem Heim-WLAN verbinden kann...")
            time.sleep(30)

            # Zurück ins Heim-WLAN wechseln
            if not reconnect_to_home_wifi(ssid):
                return cfg['intent']['smarthome'][language]['home_wifi_reconnection_failed']

            logger.info("Warte 10 Sekunden, um dem Shelly Zeit zu geben, sich mit dem Heim-WLAN zu verbinden...")
            time.sleep(10)

            current_ssid = get_current_ssid()
            if current_ssid != ssid:
                logger.error(f"Nicht mit Heim-WLAN verbunden. Aktuelle SSID: {current_ssid}")
                return cfg['intent']['smarthome'][language]['home_wifi_reconnection_failed']

            # LAN-Scan nach neuer IP-Adresse
            logger.info("Starte LAN-Scan, um neue IP-Adresse zu ermitteln...")
            shelly_info = find_shelly_ip_in_lan()
            if shelly_info:
                selected_device["ip"] = shelly_info["ip"]
                selected_device["id"] = shelly_info["id"]
                selected_device["name"] = shelly_info["name"]
                logger.info(f"Neue Shelly-Informationen: {shelly_info}")

                # Überprüfung, ob Gerät bereits existiert
                if device_already_exists(selected_device["id"]):
                    global_variables.new_smartdevice_state = None
                    global_variables.context = None
                    return random.choice(cfg['intent']['smarthome'][language]['device_exist']).format(selected_device['device'],selected_device['ip'])
            else:
                global_variables.new_smartdevice_state = None
                global_variables.context = None
                return cfg['intent']['smarthome'][language]['no_shelly_info']

        session_state["step"] += 1

        global_variables.context = new_device_name
        return cfg['intent']['smarthome'][language]['ask_device_name']


def new_device_name(user_input=''):
    if not global_variables.voice_assistant.is_listening:
        global_variables.voice_assistant.is_listening = True
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_smartdevice_state", None)

    if not session_state:
        return cfg['intent']['smarthome'][language]['no_session']

    if session_state["step"] == 2:
        global_variables.voice_assistant.is_listening = False
        if not user_input:
            return cfg['intent']['smarthome'][language]['no_device_name']

        if isinstance(session_state["selected_device"], dict):
            session_state["selected_device"]["name"] = user_input.strip().encode('utf-8').decode('utf-8')

        session_state["step"] += 1
        global_variables.context = save_new_device
        return cfg['intent']['smarthome'][language]['ask_save_new_device']


def save_new_device(user_input=''):
    if not global_variables.voice_assistant.is_listening:
        global_variables.voice_assistant.is_listening = True
    cfg, language = __read_config__()
    session_state = getattr(global_variables, "new_smartdevice_state", None)

    if not session_state:
        return cfg['intent']['smarthome'][language]['no_session']

    if session_state["step"] == 3:
        global_variables.voice_assistant.is_listening = False
        if not user_input:
            return cfg['intent']['smarthome'][language]['no_user_input']

        if user_input.strip().lower() in ["ja", "yes", "oui", "sí", "sì", "はい", "да"]:
            selected_device = session_state["selected_device"]
            marian = Translator(language, 'en')
            translated_name = marian.translate([selected_device["name"]])[0].lower()
            # Gerät speichern
            devices_table.insert({
                "id": selected_device["id"],
                "device": selected_device["device"],
                "name": translated_name,
                "type": selected_device["type"],
                "ip": selected_device["ip"]
            })
            global_variables.new_smartdevice_state = None
            global_variables.context = None  # Beende Kontext
            return random.choice(cfg['intent']['smarthome'][language]['success_add_device']).format(selected_device['name'])

        elif user_input.strip().lower() in ["nein", "no", "non", "no", "no", "いいえ", "нет"]:
            global_variables.new_smartdevice_state = None
            global_variables.context = None  # Beende Kontext
            return cfg['intent']['smarthome'][language]['end_configuration']

        else:
            return cfg['intent']['smarthome'][language]['no_user_input']


@register_call("smarthome")
def smarthome(session_id = "general", data=None):
    cfg, language = __read_config__()

    Device = Query()
    devices = devices_table.all()

    if not devices:
        logger.error("Keine Geräte in der Datenbank gefunden.")
        return cfg['intent']['smarthome'][language]['no_devices_found']

    logger.info("Devices: {}", devices)

    logger.info("Data: {}", data)

    # Split by the chosen delimiter
    args = data.split("|")

    # Assign values, handling cases where parts might be missing
    device_name = args[0].strip() if len(args) > 0 and args[0].strip() else None
    state = args[1].strip() if len(args) > 1 and args[1].strip() else None

    logger.info("device: {}", device_name)
    logger.info("state: {}", state)

    device_name = device_name.encode('utf-8').decode('utf-8')
    marian = Translator(language, 'en')
    device_name = marian.translate([device_name])[0].lower()

    # Suche das Gerät in der TinyDB
    device = devices_table.get(Device.name == device_name)

    # Gibt es das angefragte Device?
    if device:
        logger.info("Device gefunden.")
        s = None
        if state in cfg['intent']['smarthome'][language]['state_on']:
            s = "on"
        elif state in cfg['intent']['smarthome'][language]['state_off']:
            s = "off"
        else:
            logger.warning("Unbekannter Status: {}", state)
            return cfg['intent']['smarthome'][language]['state_unknown'].format(state)

        # Setze einen Get-Request ab, der das Gerät ein- oder ausschaltet
        PARAMS = {'turn': s}
        url = f"http://{device['ip']}/relay/0"

        try:
            logger.info("Device gefunden.")
            r = requests.get(url = url, params = PARAMS)
            r.raise_for_status()
            data = r.json()
            logger.debug("API-Antwort: {}", data)
            return ""
        except Exception as e:
            logger.error("Fehler beim Senden der Anfrage: {}", e)
            return cfg['intent']['smarthome'][language]['request_failed'].format(device_name)

    else:
        logger.info("Device nicht gefunden.")
        return cfg['intent']['smarthome'][language]['device_unknown'].format(device_name)
