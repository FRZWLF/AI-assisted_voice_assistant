import os
import threading

import wx
from loguru import logger
from wx.adv import TaskBarIcon

import constants


class DownloadTaskBarIcon(TaskBarIcon):
    """
    TaskBarIcon, das den Download-Status darstellt.
    """
    def __init__(self,frame, downloads, temp_files, cancel_flag):
        super().__init__()
        self.frame = frame
        self.downloads = downloads
        self.temp_files = temp_files
        self.cancel_flag = cancel_flag
        self.set_icon(constants.TRAY_ICON_DOWNLOADING, "Downloads laufen...")

    def create_menu_item(self, menu, label, func):
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.Append(item)
        return item

    def CreatePopupMenu(self):
        menu = wx.Menu()
        return menu

    def set_icon(self, path, tooltip=constants.TRAY_TOOLTIP):
        icon = wx.Icon(path)
        self.SetIcon(icon, tooltip)

    def update_tooltip(self):
        if not hasattr(self, "SetIcon"):
            return  # Das Icon wurde bereits gelöscht
        if self.downloads:
            tooltip = "\n".join([f"{lang}: {progress}%" for lang, progress in self.downloads.items()])
        else:
            tooltip = "Keine aktiven Downloads."
        self.set_icon(constants.TRAY_ICON_DOWNLOADING, tooltip)

    def on_exit(self, event):
        #logger.info("Beenden wird ausgelöst...")
        self.cancel_flag["cancel"] = True
        # Schließe alle Hintergrund-Threads
        active_threads = [t for t in threading.enumerate() if t.name.startswith("download")]
        for thread in active_threads:
            if thread.is_alive():
                logger.warning(f"Thread {thread.name} läuft noch. Warte auf Beendigung...")
                thread.join(timeout=10)
            if thread.is_alive():
                logger.error(f"Thread {thread.name} konnte nicht sauber beendet werden!")
            else:
                logger.info(f"Thread {thread.name} wurde erfolgreich beendet.")

        # Überprüfe verbleibende Threads
        remaining_threads = threading.enumerate()
        #logger.debug(f"Verbleibende Threads nach on_exit: {[t.name for t in remaining_threads]}")

        self.cleanup_temp_files()
        logger.info("Downloads beendet. Entferne Icon und beende Anwendung.")
        self.RemoveIcon()
        wx.CallAfter(self.Destroy)
        # Frame schließen, wenn vorhanden
        if self.frame:
            self.frame.Close()

    def cleanup_temp_files(self):
        print("Bereinige temporäre Dateien...")
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                print(f"Lösche Datei: {temp_file}")
                os.remove(temp_file)
        print("Alle temporären Dateien wurden entfernt.")


class DownloadApp(wx.App):
    def __init__(self, downloads, **kwargs):
        self.downloads = downloads
        self.temp_files = []
        self.cancel_flag = {"cancel": False, "temp_files": self.temp_files}
        self.all_downloads_done = False
        super().__init__(**kwargs)

    def OnInit(self):
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        self.icon = DownloadTaskBarIcon(frame, self.downloads, self.temp_files, self.cancel_flag)
        self.Bind(wx.EVT_CLOSE, self.on_close_window)
        return True

    def update_progress(self, lang, progress):
        if lang in self.downloads:
            self.downloads[lang] = progress
            self.icon.update_tooltip()

        # Prüfen, ob alle Downloads abgeschlossen sind
        if all(p == 100 for p in self.downloads.values()):
            self.on_all_downloads_complete()

    def on_all_downloads_complete(self):
        #logger.info("Alle Downloads abgeschlossen. DownloadApp wird beendet.")
        self.all_downloads_done = True
        self.icon.RemoveIcon()
        wx.CallAfter(self.ExitMainLoop)

    def on_close_window(self, evt):
        self.icon.on_exit(None)
        self.icon.Destroy()