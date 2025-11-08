#!/usr/bin/python3
import sys
import requests
import json
import time
import os
from collections import defaultdict 

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLineEdit, QPushButton, QLabel, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QFrame, QFormLayout,
    QHBoxLayout, QComboBox, QAbstractItemView,
    QSystemTrayIcon, QMenu, QCheckBox, QHeaderView
)
from PyQt6.QtCore import QThread, pyqtSignal, QSettings, Qt, QEvent 
from PyQt6.QtGui import QIcon, QAction

# Checks if the application is running as a "frozen" .exe
if getattr(sys, 'frozen', False):
    # If frozen, path is the .exe folder
    APP_DIR = os.path.dirname(sys.executable)
elif __file__:
    # If running as .py, use the old method
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Thread Classes ---

# --- POCZĄTEK MODYFIKACJI (PRZYWRÓCONA KLASA) ---
class GetAppsThread(QThread):
    """Separate thread to fetch the installed application list."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, ip_address):
        super().__init__()
        self.ip_address = ip_address

    def run(self):
        try:
            url = f"http://{self.ip_address}:9529/ZidooControlCenter/Apps/getApps"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 200:
                app_list = data.get("list", data.get("apps", data.get("appList")))
                
                if isinstance(app_list, list):
                    self.finished.emit(app_list)
                else:
                    self.error.emit("Invalid data structure (missing 'list' or 'apps')")
            else:
                self.error.emit(f"API returned error: {data.get('msg', 'Unknown error')}")
        except Exception as e:
            self.error.emit(f"Error fetching apps: {e}")
# --- KONIEC MODYFIKACJI ---

class RemoteControlThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, ip_address, key):
        super().__init__()
        self.ip_address = ip_address
        self.key = key
    def run(self):
        try:
            url = f"http://{self.ip_address}:9529/ZidooControlCenter/RemoteControl/sendkey"
            params = {'key': self.key}
            response = requests.get(url, params=params, timeout=3)
            response.raise_for_status(); data = response.json()
            if data.get('status') == 200: self.finished.emit(f"Sent key: {self.key}")
            else: self.error.emit(f"API Error ({self.key}): {data.get('msg', 'None')}")
        except Exception as e: self.error.emit(f"Error sending key {self.key}: {e}")

class OpenFileThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, ip_address, full_path):
        super().__init__()
        self.ip_address = ip_address
        self.full_path = full_path
    def run(self):
        try:
            url = f"http://{self.ip_address}:9529/ZidooFileControl/openFile"
            params = {'path': self.full_path}
            response = requests.get(url, params=params, timeout=3)
            response.raise_for_status(); data = response.json()
            if data.get('status') == 200: self.finished.emit("Command 'Open file' sent.")
            else: self.error.emit(f"API returned error: {data.get('msg', 'Unknown error')}")
        except Exception as e: self.error.emit(f"Error sending 'openFile' command: {e}")

class GetDevicesThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    def __init__(self, ip_address):
        super().__init__()
        self.ip_address = ip_address
    def run(self):
        try:
            url = f"http://{self.ip_address}:9529/ZidooFileControl/getDevices"
            response = requests.get(url, timeout=3)
            response.raise_for_status(); data = response.json()
            if data.get('status') == 200:
                device_list = data.get("devices", data.get("list")) 
                if isinstance(device_list, list): self.finished.emit(device_list)
                else: self.error.emit("Invalid data structure (missing 'devices' or 'list')")
            else: self.error.emit(f"API returned error: {data.get('msg', 'Unknown error')}")
        except Exception as e: self.error.emit(f"Error fetching devices: {e}")

class PlayerControlThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, ip_address, command):
        super().__init__()
        self.ip_address = ip_address
        self.command = command
    def run(self):
        try:
            url = f"http://{self.ip_address}:9529/ZidooMusicControl/{self.command}"
            response = requests.get(url, timeout=3)
            response.raise_for_status(); data = response.json()
            if data.get('status') == 200: self.finished.emit(f"Command sent: {self.command}")
            else: self.error.emit(f"API Error ({self.command}): {data.get('msg', 'None')}")
        except Exception as e: self.error.emit(f"Command error ({self.command}): {e}")

class GetModelThread(QThread):
    finished = pyqtSignal(dict) 
    error = pyqtSignal(str)     
    def __init__(self, ip_address):
        super().__init__()
        self.ip_address = ip_address
    def run(self):
        try:
            url = f"http://{self.ip_address}:9529/ZidooControlCenter/getModel"
            response = requests.get(url, timeout=3)
            response.raise_for_status(); data = response.json()
            if data.get('status') == 200: self.finished.emit(data)
            else: self.error.emit(f"API returned error: {data.get('msg', 'Unknown error')}")
        except Exception as e: self.error.emit(f"Error fetching model: {e}")

class MusicFetcherThread(QThread):
    progress_update = pyqtSignal(str) 
    finished = pyqtSignal(list)       
    error = pyqtSignal(str)           
    def __init__(self, ip_address):
        super().__init__()
        self.ip_address = ip_address
        self.page_size = 100
        self.is_running = True
    def run(self):
        all_music_files = []
        current_folder_id = 1
        try:
            while self.is_running:
                current_page = 1
                while self.is_running:
                    self.progress_update.emit(f"Scanning Folder {current_folder_id}, Page {current_page}...")
                    try:
                        base_url = f"http://{self.ip_address}:9529/ZidooMusicControl/getMusics"
                        params = {
                            'folderId': current_folder_id, 
                            'page': current_page, 
                            'pagesize': self.page_size
                        }
                        response = requests.get(base_url, params=params, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        if data.get('status') != 200:
                            raise Exception(f"API Error: {data.get('msg', 'Unknown')}")
                        music_list = data.get("musics") 
                        if music_list:
                            all_music_files.extend(music_list)
                            current_page += 1
                            time.sleep(0.1) 
                        else:
                            self.progress_update.emit(f"Folder {current_folder_id} finished.")
                            break
                    except Exception as e:
                        if current_page == 1:
                            self.progress_update.emit(f"Folder {current_folder_id} invalid or scan complete. Stopping.")
                            self.is_running = False
                        else:
                            self.progress_update.emit(f"Finished folder {current_folder_id} (Page {current_page} error).")
                            break
                if not self.is_running:
                    break
                current_folder_id += 1
            self.progress_update.emit("Collection scan finished.")
            self.finished.emit(all_music_files)
        except Exception as e:
            self.error.emit(f"Fatal error during music download: {e}")
    def stop(self): self.is_running = False

# --- Main Application Class ---
class EveRApp(QMainWindow): 
    
    def __init__(self):
        super().__init__()
        self.music_fetcher_thread = None 
        self.model_fetcher_thread = None
        self.open_file_thread = None
        self.play_control_thread = None
        self.devices_fetcher_thread = None
        self.remote_control_thread = None
        self.apps_fetcher_thread = None
        
        self.config_tab_index = -1
        self.apps_tab_index = -1
        self.current_base_path = ""
        
        self.is_quitting = False
        self.tray_enabled = True
        
        self.artist_tree = QTreeWidget()
        self.album_tree = QTreeWidget()
        
        self.artist_search_bar = QLineEdit()
        self.artist_prev_button = QPushButton("<")
        self.artist_next_button = QPushButton(">")
        self.album_search_bar = QLineEdit()
        self.album_prev_button = QPushButton("<")
        self.album_next_button = QPushButton(">")
        
        self.artist_search_matches = []
        self.artist_search_index = -1
        self.album_search_matches = []
        self.album_search_index = -1
        
        self.ip_label = QLabel('Enter EverSolo device IP address:')
        self.ip_input = QLineEdit()
        self.connect_button = QPushButton("Connect")
        self.devices_label = QLabel("Select device (drive):")
        self.devices_combo = QComboBox()
        self.start_button = QPushButton("Refresh collection from device")
        
        self.tray_enabled_checkbox = QCheckBox("Enable icon tray")
        
        self.model_field = QLineEdit()
        self.firmware_field = QLineEdit()
        self.net_mac_field = QLineEdit()
        self.wifi_mac_field = QLineEdit()
        self.android_field = QLineEdit()
        self.ram_field = QLineEdit()
        self.flash_field = QLineEdit()
        
        self.config_tabs = QTabWidget()
        self.refresh_apps_button = QPushButton("Refresh apps from device")
        self.apps_tree = QTreeWidget()
        
        self.play_button = QPushButton("Play >")
        self.pause_button = QPushButton("Pause ||")
        self.prev_button = QPushButton("<< Prev")
        self.next_button = QPushButton("Next >>")
        self.vol_up_button = QPushButton("Vol+")
        self.vol_down_button = QPushButton("Vol-")
        
        self.tray_icon = QSystemTrayIcon(self)
        
        self.initUI()

    def initUI(self):
        self.setWindowTitle('EveR - Music Collection')
        self.setGeometry(300, 300, 500, 500) 

        icon_path = os.path.join(APP_DIR, "logo.png")
        app_icon = QIcon(icon_path)
        
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        else:
            print(f"Warning: Icon file not found at {icon_path}. Using default icon.", file=sys.stderr)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        self.load_settings()
        
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        tabs.currentChanged.connect(self.on_tab_changed)

        # "Album Artists" Tab
        artist_tab_widget = QWidget()
        artist_tab_layout = QVBoxLayout()
        artist_tab_layout.setContentsMargins(0, 5, 0, 0)
        artist_tab_widget.setLayout(artist_tab_layout)
        artist_search_layout = QHBoxLayout()
        self.artist_search_bar.setPlaceholderText("Search Artists, Albums, or Tracks...")
        self.artist_search_bar.textChanged.connect(self.on_search_text_changed)
        self.artist_prev_button.setFixedWidth(30)
        self.artist_next_button.setFixedWidth(30)
        self.artist_prev_button.clicked.connect(self.on_prev_match)
        self.artist_next_button.clicked.connect(self.on_next_match)
        artist_search_layout.addWidget(self.artist_search_bar)
        artist_search_layout.addWidget(self.artist_prev_button)
        artist_search_layout.addWidget(self.artist_next_button)
        artist_tab_layout.addLayout(artist_search_layout)
        self.artist_tree.setColumnCount(5)
        self.artist_tree.setHeaderLabels(["Title", "Duration", "SRate", "BRate", "Type"])
        self.artist_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.artist_tree.header().resizeSection(1, 70)
        self.artist_tree.header().resizeSection(2, 60)
        self.artist_tree.header().resizeSection(3, 60)
        self.artist_tree.header().resizeSection(4, 60)
        self.artist_tree.header().setStretchLastSection(False)
        self.artist_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.artist_tree.itemExpanded.connect(self.on_artist_tree_item_expanded)
        artist_tab_layout.addWidget(self.artist_tree)
        tabs.addTab(artist_tab_widget, "Album Artists")

        # "Albums" Tab
        album_tab_widget = QWidget()
        album_tab_layout = QVBoxLayout()
        album_tab_layout.setContentsMargins(0, 5, 0, 0)
        album_tab_widget.setLayout(album_tab_layout)
        album_search_layout = QHBoxLayout()
        self.album_search_bar.setPlaceholderText("Search Albums or Tracks...")
        self.album_search_bar.textChanged.connect(self.on_search_text_changed)
        self.album_prev_button.setFixedWidth(30)
        self.album_next_button.setFixedWidth(30)
        self.album_prev_button.clicked.connect(self.on_prev_match)
        self.album_next_button.clicked.connect(self.on_next_match)
        album_search_layout.addWidget(self.album_search_bar)
        album_search_layout.addWidget(self.album_prev_button)
        album_search_layout.addWidget(self.album_next_button)
        album_tab_layout.addLayout(album_search_layout)
        self.album_tree.setColumnCount(5)
        self.album_tree.setHeaderLabels(["Title", "Duration", "SRate", "BRate", "Type"])
        self.album_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.album_tree.header().resizeSection(1, 70)
        self.album_tree.header().resizeSection(2, 60)
        self.album_tree.header().resizeSection(3, 60)
        self.album_tree.header().resizeSection(4, 60)
        self.album_tree.header().setStretchLastSection(False)
        self.album_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.album_tree.itemExpanded.connect(self.on_album_tree_item_expanded)
        album_tab_layout.addWidget(self.album_tree)
        tabs.addTab(album_tab_widget, "Albums")

        # "Configuration" Tab
        config_tab = QWidget()
        config_layout = QVBoxLayout()
        config_tab.setLayout(config_layout)
        config_layout.addWidget(self.config_tabs)
        self.config_tabs.currentChanged.connect(self.on_config_sub_tab_changed)
        # 1. Pod-zakładka "Main"
        main_config_tab = QWidget()
        main_config_layout = QVBoxLayout()
        main_config_tab.setLayout(main_config_layout)
        main_config_layout.addWidget(self.ip_label)
        ip_entry_layout = QHBoxLayout()
        self.ip_input.setPlaceholderText('e.g., 192.168.1.100')
        ip_entry_layout.addWidget(self.ip_input)
        self.connect_button.setFixedWidth(80)
        self.connect_button.clicked.connect(self.on_connect_button_clicked)
        ip_entry_layout.addWidget(self.connect_button)
        main_config_layout.addLayout(ip_entry_layout)
        main_config_layout.addWidget(self.devices_label)
        self.devices_combo.currentIndexChanged.connect(self.on_device_selection_changed)
        main_config_layout.addWidget(self.devices_combo)
        self.start_button.clicked.connect(self.start_music_fetching)
        main_config_layout.addWidget(self.start_button)
        self.tray_enabled_checkbox.stateChanged.connect(self.on_tray_setting_changed)
        main_config_layout.addWidget(self.tray_enabled_checkbox)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_config_layout.addWidget(separator)
        form_layout = QFormLayout()
        self.model_field.setReadOnly(True); form_layout.addRow(QLabel("Model:")); form_layout.addRow(self.model_field)
        self.firmware_field.setReadOnly(True); form_layout.addRow(QLabel("Firmware:")); form_layout.addRow(self.firmware_field)
        self.android_field.setReadOnly(True); form_layout.addRow(QLabel("Android:")); form_layout.addRow(self.android_field)
        self.net_mac_field.setReadOnly(True); form_layout.addRow(QLabel("MAC (LAN):")); form_layout.addRow(self.net_mac_field)
        self.wifi_mac_field.setReadOnly(True); form_layout.addRow(QLabel("MAC (Wi-Fi):")); form_layout.addRow(self.wifi_mac_field)
        self.ram_field.setReadOnly(True); form_layout.addRow(QLabel("RAM:")); form_layout.addRow(self.ram_field)
        self.flash_field.setReadOnly(True); form_layout.addRow(QLabel("Flash:")); form_layout.addRow(self.flash_field)
        main_config_layout.addLayout(form_layout)
        main_config_layout.addStretch()
        # 2. Pod-zakładka "Apps"
        apps_tab = QWidget()
        apps_layout = QVBoxLayout()
        apps_tab.setLayout(apps_layout)
        self.refresh_apps_button.clicked.connect(self.fetch_apps_list)
        apps_layout.addWidget(self.refresh_apps_button)
        self.apps_tree.setColumnCount(4)
        self.apps_tree.setHeaderLabels(["App Name", "Package Name", "Version", "System App"])
        self.apps_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.apps_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        apps_layout.addWidget(self.apps_tree)
        self.config_tabs.addTab(main_config_tab, "Main")
        self.apps_tab_index = self.config_tabs.addTab(apps_tab, "Apps")
        self.config_tab_index = tabs.addTab(config_tab, "Configuration")

        # Player Control Buttons
        button_layout = QHBoxLayout()
        self.prev_button.clicked.connect(lambda: self.send_player_command("playPrevious"))
        self.play_button.clicked.connect(lambda: self.send_player_command("start"))
        self.pause_button.clicked.connect(lambda: self.send_player_command("pause"))
        self.next_button.clicked.connect(lambda: self.send_player_command("playNext"))
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)
        main_layout.addLayout(button_layout)
        
        # Volume Control Buttons
        volume_button_layout = QHBoxLayout()
        self.vol_up_button.clicked.connect(lambda: self.send_remote_key_command("Key.VolumeUp"))
        self.vol_down_button.clicked.connect(lambda: self.send_remote_key_command("Key.VolumeDown"))
        volume_button_layout.addWidget(self.vol_down_button)
        volume_button_layout.addWidget(self.vol_up_button)
        main_layout.addLayout(volume_button_layout)
        
        self.statusBar().showMessage("Ready")
        
        self.setup_tray_icon(app_icon)
        self.load_collection_from_file()

    # --- Settings and Window State Handling (bez zmian) ---
    def setup_tray_icon(self, icon: QIcon):
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("EveR - Music Collection")
        tray_menu = QMenu(self)
        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.show_and_raise)
        tray_menu.addAction(restore_action)
        tray_menu.addSeparator()
        prev_action = QAction("Previous Track", self)
        prev_action.triggered.connect(lambda: self.send_player_command("playPrevious"))
        tray_menu.addAction(prev_action)
        next_action = QAction("Next Track", self)
        next_action.triggered.connect(lambda: self.send_player_command("playNext"))
        tray_menu.addAction(next_action)
        tray_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.setVisible(self.tray_enabled)

    def show_and_raise(self):
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_and_raise()

    def changeEvent(self, event: QEvent):
        if self.tray_enabled and event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                event.ignore()
                self.hide()
                return
        super().changeEvent(event)

    def quit_application(self):
        self.is_quitting = True
        QApplication.instance().quit()

    def closeEvent(self, event: QEvent | None):
        config_path = self.get_config_ini_path()
        settings = QSettings(config_path, QSettings.Format.IniFormat)
        settings.setValue("last_ip", self.ip_input.text().strip())
        settings.setValue("window_geometry", self.saveGeometry())
        settings.setValue("tray_enabled", self.tray_enabled_checkbox.isChecked())
        self.save_device_setting(self.devices_combo.currentData())
        
        if self.is_quitting or not self.tray_enabled:
            self.tray_icon.hide()
            if self.music_fetcher_thread and self.music_fetcher_thread.isRunning():
                self.music_fetcher_thread.stop()
                self.music_fetcher_thread.wait()
            if event:
                event.accept()
        else:
            if event:
                event.ignore()
            self.hide()

    def load_settings(self):
        config_path = self.get_config_ini_path()
        settings = QSettings(config_path, QSettings.Format.IniFormat)
        
        last_ip = settings.value("last_ip", "")
        self.ip_input.setText(last_ip)
        
        geometry = settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        last_path = settings.value("last_path", "")
        self.current_base_path = last_path
        
        self.tray_enabled = settings.value("tray_enabled", True, type=bool) 
        self.tray_enabled_checkbox.setChecked(self.tray_enabled)
        
        QApplication.instance().setQuitOnLastWindowClosed(not self.tray_enabled)

    def save_settings(self, ip_address):
        config_path = self.get_config_ini_path()
        settings = QSettings(config_path, QSettings.Format.IniFormat)
        settings.setValue("last_ip", ip_address)

    def save_device_setting(self, path: str | None):
        if path:
            self.current_base_path = path
            config_path = self.get_config_ini_path()
            settings = QSettings(config_path, QSettings.Format.IniFormat)
            settings.setValue("last_path", path)
            
    def on_tray_setting_changed(self, state):
        self.tray_enabled = (state == Qt.CheckState.Checked.value)
        QApplication.instance().setQuitOnLastWindowClosed(not self.tray_enabled)
        self.tray_icon.setVisible(self.tray_enabled)
        
        config_path = self.get_config_ini_path()
        settings = QSettings(config_path, QSettings.Format.IniFormat)
        settings.setValue("tray_enabled", self.tray_enabled)

    # --- Thread Logic and UI Slots ---
    def on_connect_button_clicked(self):
        self.fetch_model_info()
        self.fetch_devices_info()
    
    def on_search_text_changed(self, text):
        sender = self.sender()
        if sender is self.artist_search_bar:
            target_tree = self.artist_tree
            matches_list = self.artist_search_matches
            index_attr = 'artist_search_index'
        elif sender is self.album_search_bar:
            target_tree = self.album_tree
            matches_list = self.album_search_matches
            index_attr = 'album_search_index'
        else:
            return

        target_tree.clearSelection()
        matches_list.clear()
        setattr(self, index_attr, -1)

        if len(text) < 3:
            return

        search_flags = Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive
        matches = target_tree.findItems(text, search_flags, 0)
        
        if matches:
            matches_list.extend(matches)
            setattr(self, index_attr, 0)
            self.select_and_scroll_to_item(target_tree, matches_list[0])

    def on_next_match(self):
        sender = self.sender()
        if sender is self.artist_next_button:
            target_tree = self.artist_tree
            matches_list = self.artist_search_matches
            index_attr = 'artist_search_index'
            current_index = self.artist_search_index
        elif sender is self.album_next_button:
            target_tree = self.album_tree
            matches_list = self.album_search_matches
            index_attr = 'album_search_index'
            current_index = self.album_search_index
        else:
            return
        if not matches_list: return
        new_index = (current_index + 1) % len(matches_list)
        setattr(self, index_attr, new_index)
        self.select_and_scroll_to_item(target_tree, matches_list[new_index])

    def on_prev_match(self):
        sender = self.sender()
        if sender is self.artist_prev_button:
            target_tree = self.artist_tree
            matches_list = self.artist_search_matches
            index_attr = 'artist_search_index'
            current_index = self.artist_search_index
        elif sender is self.album_prev_button:
            target_tree = self.album_tree
            matches_list = self.album_search_matches
            index_attr = 'album_search_index'
            current_index = self.album_search_index
        else:
            return
        if not matches_list: return
        new_index = (current_index - 1) % len(matches_list)
        setattr(self, index_attr, new_index)
        self.select_and_scroll_to_item(target_tree, matches_list[new_index])

    def select_and_scroll_to_item(self, tree: QTreeWidget, item: QTreeWidgetItem):
        parent = item.parent()
        while parent:
            parent.setExpanded(True)
            parent = parent.parent()
        tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtTop)
        tree.setCurrentItem(item)
    
    def on_artist_tree_item_expanded(self, expanded_item: QTreeWidgetItem):
        self.artist_tree.blockSignals(True)
        parent = expanded_item.parent()
        if parent is None:
            parent = self.artist_tree.invisibleRootItem()
        for i in range(parent.childCount()):
            sibling = parent.child(i)
            if sibling is not expanded_item and sibling.isExpanded():
                sibling.setExpanded(False)
        self.artist_tree.blockSignals(False)

    def on_album_tree_item_expanded(self, expanded_item: QTreeWidgetItem):
        self.album_tree.blockSignals(True)
        parent = expanded_item.parent()
        if parent is None:
            parent = self.album_tree.invisibleRootItem()
        for i in range(parent.childCount()):
            sibling = parent.child(i)
            if sibling is not expanded_item and sibling.isExpanded():
                sibling.setExpanded(False)
        self.album_tree.blockSignals(False)

    def on_item_double_clicked(self, item, column):
        track_to_play_uri = None
        tree = item.treeWidget()
        parent = item.parent()
        if parent is None:
            if tree is self.album_tree:
                if item.childCount() > 0:
                    first_track_item = item.child(0)
                    track_to_play_uri = first_track_item.data(0, Qt.ItemDataRole.UserRole)
                    self.statusBar().showMessage(f"Playing first track from album: {item.text(0)}...")
                else:
                    self.statusBar().showMessage(f"Album {item.text(0)} is empty.")
                    return
            else:
                return
        elif parent.parent() is None:
            if tree is self.artist_tree:
                if item.childCount() > 0:
                    first_track_item = item.child(0)
                    track_to_play_uri = first_track_item.data(0, Qt.ItemDataRole.UserRole)
                    self.statusBar().showMessage(f"Playing first track from album: {item.text(0)}...")
                else:
                    self.statusBar().showMessage(f"Album {item.text(0)} is empty.")
                    return
            else:
                track_to_play_uri = item.data(0, Qt.ItemDataRole.UserRole)
        else:
            track_to_play_uri = item.data(0, Qt.ItemDataRole.UserRole) 

        if track_to_play_uri is None:
            self.statusBar().showMessage("ERROR: 'uri' not found for this track.")
            return
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.statusBar().showMessage("ERROR: Please enter an IP address in Configuration.")
            return
        base_path = self.current_base_path
        if not base_path:
             self.statusBar().showMessage("ERROR: Select a valid device in Configuration.")
             return
        full_path = base_path.rstrip("/") + track_to_play_uri
        self.statusBar().showMessage(f"Opening: {full_path}...")
        self.open_file_thread = OpenFileThread(ip_address, full_path)
        self.open_file_thread.finished.connect(self.on_command_success)
        self.open_file_thread.error.connect(self.on_command_error)
        self.open_file_thread.start()

    def on_command_success(self, message):
        self.statusBar().showMessage(message, 5000)

    def on_command_error(self, error_message):
        self.statusBar().showMessage(f"ERROR: {error_message}", 10000)

    def on_tab_changed(self, index):
        self.artist_search_bar.clear()
        self.album_search_bar.clear()
        self.artist_search_matches.clear()
        self.artist_search_index = -1
        self.album_search_matches.clear()
        self.album_search_index = -1
        
        if index == self.config_tab_index:
            sub_index = self.config_tabs.currentIndex()
            self.on_config_sub_tab_changed(sub_index)

    def on_config_sub_tab_changed(self, sub_index):
        """Called when switching between 'Main' and 'Apps'."""
        if sub_index == 0: # "Main"
            self.on_connect_button_clicked()
        elif sub_index == self.apps_tab_index: # "Apps"
            self.fetch_apps_list()

    def fetch_devices_info(self):
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            return
        self.devices_combo.clear()
        self.devices_combo.addItem("Fetching...")
        self.statusBar().showMessage("Fetching device list...")
        self.devices_fetcher_thread = GetDevicesThread(ip_address)
        self.devices_fetcher_thread.finished.connect(self.on_devices_fetch_success)
        self.devices_fetcher_thread.error.connect(self.on_devices_fetch_error)
        self.devices_fetcher_thread.start()

    def on_devices_fetch_success(self, device_list):
        self.devices_combo.blockSignals(True)
        self.devices_combo.clear()
        if not device_list:
            self.devices_combo.addItem("No devices found")
            self.devices_combo.blockSignals(False)
            return
        for device in device_list:
            name = device.get("name", "Unnamed")
            path = device.get("path", "No path")
            display_text = f"{name} [{path}]"
            self.devices_combo.addItem(display_text, userData=path) 
        self.statusBar().showMessage("Successfully fetched device list.", 3000)
        try:
            if self.current_base_path:
                index = self.devices_combo.findData(self.current_base_path)
                if index > -1:
                    self.devices_combo.setCurrentIndex(index)
        except Exception as e:
            self.statusBar().showMessage(f"Error restoring device selection: {e}", 5000)
        self.devices_combo.blockSignals(False)

    def on_device_selection_changed(self, index):
        if index == -1: return
        path = self.devices_combo.itemData(index)
        self.save_device_setting(path)

    def on_devices_fetch_error(self, error_message):
        self.statusBar().showMessage(error_message, 5000)
        self.devices_combo.clear()
        self.devices_combo.addItem(f"Error")

    def fetch_model_info(self):
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            return
        self.clear_model_info_fields()
        self.statusBar().showMessage("Fetching model info...")
        self.model_fetcher_thread = GetModelThread(ip_address)
        self.model_fetcher_thread.finished.connect(self.on_model_fetch_success)
        self.model_fetcher_thread.error.connect(self.on_model_fetch_error)
        self.model_fetcher_thread.start()

    def fetch_apps_list(self):
        """Uruchamia wątek 'getApps'."""
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.statusBar().showMessage("No IP. Cannot fetch apps list.")
            return
            
        self.apps_tree.clear()
        self.statusBar().showMessage("Fetching application list...")
        
        self.apps_fetcher_thread = GetAppsThread(ip_address)
        self.apps_fetcher_thread.finished.connect(self.on_apps_fetch_success)
        self.apps_fetcher_thread.error.connect(self.on_apps_fetch_error)
        self.apps_fetcher_thread.start()

    def on_apps_fetch_success(self, app_list):
        """Wypełnia tabelę 'Apps'."""
        self.apps_tree.clear()
        self.statusBar().showMessage(f"Successfully fetched {len(app_list)} apps.", 3000)
        
        for app in app_list:
            label = app.get("label", "N/A")
            package = app.get("packageName", "N/A")
            version = app.get("versionName", "N/A")
            
            is_system = app.get("isSystemApp")
            if is_system is True or is_system == 1 or str(is_system).lower() == 'true':
                system_app_str = "Yes"
            else:
                system_app_str = "No"
                
            item = QTreeWidgetItem([label, package, version, system_app_str])
            self.apps_tree.addTopLevelItem(item)

    def on_apps_fetch_error(self, error_message):
        """Obsługuje błąd pobierania listy aplikacji."""
        self.statusBar().showMessage(error_message, 5000)
        self.apps_tree.clear()

    def clear_model_info_fields(self):
        self.model_field.clear()
        self.firmware_field.clear()
        self.net_mac_field.clear()
        self.wifi_mac_field.clear()
        self.android_field.clear()
        self.ram_field.clear()
        self.flash_field.clear()

    def on_model_fetch_success(self, data):
        self.statusBar().showMessage("Successfully fetched model info.", 5000)
        self.model_field.setText(data.get("model", "N/A"))
        self.firmware_field.setText(data.get("firmware", "N/A"))
        self.net_mac_field.setText(data.get("net_mac", "N/A"))
        self.wifi_mac_field.setText(data.get("wif_mac", "N/A"))
        self.android_field.setText(data.get("androidversion", "N/A"))
        self.ram_field.setText(data.get("ram", "N/A").strip())
        self.flash_field.setText(data.get("flash", "N/A").strip())

    def on_model_fetch_error(self, error_message):
        self.statusBar().showMessage(error_message)
        self.clear_model_info_fields()

    # --- Collection Handling (Loading, Saving, Processing) ---
    def get_collection_json_path(self):
        return os.path.join(APP_DIR, "music_collection.json")

    def get_config_ini_path(self):
        return os.path.join(APP_DIR, "config.ini")

    def load_collection_from_file(self):
        file_path = self.get_collection_json_path()
        try:
            if os.path.exists(file_path):
                self.statusBar().showMessage(f"Loading: {file_path}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                artists_map = data.get("artists_map", {})
                albums_map = data.get("albums_map", {}) 
                self.populate_trees(artists_map, albums_map)
                self.statusBar().showMessage(f"Collection loaded from file ({len(artists_map)} artists).", 5000)
            else:
                self.statusBar().showMessage("Welcome! Click refresh to fetch the collection.", 5000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to load collection file: {e}")

    def save_collection_to_file(self, artists_map, albums_map):
        file_path = self.get_collection_json_path()
        try:
            self.statusBar().showMessage(f"Saving collection to: {file_path}...")
            data_to_save = {
                "artists_map": artists_map,
                "albums_map": albums_map
            }
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            self.statusBar().showMessage("Collection saved.", 5000)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to save collection: {e}")

    def start_music_fetching(self):
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.statusBar().showMessage("ERROR: Please enter an IP address.")
            return
        self.save_settings(ip_address)
        self.start_button.setEnabled(False)
        self.start_button.setText("Downloading...")
        self.statusBar().showMessage(f"Starting download from {ip_address}...")
        self.music_fetcher_thread = MusicFetcherThread(ip_address)
        self.music_fetcher_thread.progress_update.connect(self.update_progress)
        self.music_fetcher_thread.finished.connect(self.on_fetching_finished)
        self.music_fetcher_thread.error.connect(self.on_fetching_error)
        self.music_fetcher_thread.start() 

    def update_progress(self, message):
        self.statusBar().showMessage(message) 

    def process_music_list(self, music_list):
        artists_map_builder = defaultdict(lambda: defaultdict(list))
        albums_map_builder = defaultdict(list)
        default_artist = "Unknown Artist"
        default_album = "Unknown Album"
        for track in music_list:
            artist = track.get('albumArtist') or default_artist
            album = track.get('album') or default_album
            artists_map_builder[artist][album].append(track)
            albums_map_builder[album].append(track)
        final_artists_map = dict(artists_map_builder)
        final_albums_map = dict(albums_map_builder)
        return final_artists_map, final_albums_map

    def populate_trees(self, artists_map, albums_map):
        
        self.artist_search_bar.clear()
        self.album_search_bar.clear()
        self.artist_search_matches.clear()
        self.artist_search_index = -1
        self.album_search_matches.clear()
        self.album_search_index = -1
        
        self.artist_tree.clear()
        self.album_tree.clear()
        
        sorted_artists = sorted(artists_map.keys())
        for artist_name in sorted_artists:
            artist_item = QTreeWidgetItem([artist_name])
            artist_item.setFirstColumnSpanned(True)
            self.artist_tree.addTopLevelItem(artist_item)
            
            albums_dict = artists_map[artist_name]
            sorted_albums = sorted(albums_dict.keys())
            
            for album_name in sorted_albums:
                tracks_list = albums_dict[album_name]
                album_date = ""
                artist_for_tooltip = artist_name
                if tracks_list:
                    album_date = tracks_list[0].get('date') or "N/A"
                else:
                    album_date = "N/A"
                album_display_text = f"{album_name} ({album_date})" if album_date != "N/A" else album_name
                
                album_item = QTreeWidgetItem([album_display_text])
                album_item.setFirstColumnSpanned(True)
                
                album_tooltip = f"Artist: {artist_for_tooltip}\nDate: {album_date}"
                album_item.setToolTip(0, album_tooltip)
                artist_item.addChild(album_item)
                
                sorted_tracks = sorted(
                    tracks_list, 
                    key=lambda t: t.get('number') if t.get('number') is not None else 999
                )
                
                for track_obj in sorted_tracks:
                    number_str, title_str, duration_str, tooltip_str, srate_str, brate_str, file_type_str = self.format_track_parts(track_obj)
                    
                    col_0_text = f"{number_str}. {title_str}"
                    track_item = QTreeWidgetItem([col_0_text, duration_str, srate_str, brate_str, file_type_str])
                    
                    track_item.setToolTip(0, tooltip_str)
                    track_item.setToolTip(1, tooltip_str)
                    track_item.setToolTip(2, tooltip_str)
                    track_item.setToolTip(3, tooltip_str)
                    track_item.setToolTip(4, tooltip_str)
                    
                    track_uri = track_obj.get('uri')
                    if track_uri is not None:
                        track_item.setData(0, Qt.ItemDataRole.UserRole, track_uri) 
                    album_item.addChild(track_item)
                    
        sorted_albums_flat = sorted(albums_map.keys())
        
        for album_name in sorted_albums_flat:
            tracks_list = albums_map[album_name]
            album_date = ""
            artist_for_tooltip = "Unknown Artist"
            if tracks_list:
                album_date = tracks_list[0].get('date') or "N/A"
                artist_for_tooltip = tracks_list[0].get('albumArtist') or "Unknown Artist"
            else:
                 album_date = "N/A"
            album_display_text = f"{album_name} ({album_date})" if album_date != "N/A" else album_name
            
            album_item = QTreeWidgetItem([album_display_text])
            album_item.setFirstColumnSpanned(True)
            
            album_tooltip = f"Artist: {artist_for_tooltip}\nDate: {album_date}"
            album_item.setToolTip(0, album_tooltip)
            self.album_tree.addTopLevelItem(album_item)
            
            sorted_tracks = sorted(
                tracks_list, 
                key=lambda t: t.get('number') if t.get('number') is not None else 999
            )
            
            for track_obj in sorted_tracks:
                number_str, title_str, duration_str, tooltip_str, srate_str, brate_str, file_type_str = self.format_track_parts(track_obj)
                
                col_0_text = f"{number_str}. {title_str}"
                track_item = QTreeWidgetItem([col_0_text, duration_str, srate_str, brate_str, file_type_str])

                track_item.setToolTip(0, tooltip_str)
                track_item.setToolTip(1, tooltip_str)
                track_item.setToolTip(2, tooltip_str)
                track_item.setToolTip(3, tooltip_str)
                track_item.setToolTip(4, tooltip_str)
                
                track_uri = track_obj.get('uri')
                if track_uri is not None:
                    track_item.setData(0, Qt.ItemDataRole.UserRole, track_uri)
                album_item.addChild(track_item)

    def format_track_parts(self, track_obj):
        title = track_obj.get('fileName', 'Unknown Track')
        number_val = track_obj.get('number')
        duration_ms = track_obj.get('duration')
        artist = track_obj.get('artist') or 'Unknown Artist'
        album = track_obj.get('album') or 'Unknown Album'
        date = track_obj.get('date') or 'N/A'
        file_type = track_obj.get('extension', 'N/A').upper()
        samplerate_val = track_obj.get('SampleRate')
        bitrate_val = track_obj.get('bitrate')

        number_display = "?"
        try:
            num = int(number_val) 
            if num < 10: number_display = f"0{num}"
            else: number_display = str(num)
        except (ValueError, TypeError): number_display = "?"

        duration_display = ""
        if isinstance(duration_ms, int):
            try:
                total_seconds = int(duration_ms / 1000)
                minutes, seconds = divmod(total_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    duration_display = f"{hours}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_display = f"{minutes:02d}:{seconds:02d}"
            except Exception:
                duration_display = ""
        
        samplerate_display = "N/A"
        if isinstance(samplerate_val, int) and samplerate_val > 0:
            try:
                samplerate_k = samplerate_val / 1000.0
                samplerate_display = f"{samplerate_k:.1f}k".replace(".0k","k") 
            except Exception: pass

        bitrate_display = "N/A"
        if isinstance(bitrate_val, int) and bitrate_val > 0:
            try:
                bitrate_k = int(bitrate_val / 1000)
                bitrate_display = f"{bitrate_k}k"
            except Exception: pass

        track_tooltip_text = (
            f"Artist: {artist}\n"
            f"Album: {album}\n"
            f"Date: {date}\n"
            f"Type: {file_type}\n"
            f"Sample Rate: {samplerate_display}\n"
            f"Bitrate: {bitrate_display}"
        )
        
        return number_display, title, duration_display, track_tooltip_text, samplerate_display, bitrate_display, file_type

    def on_fetching_finished(self, music_list):
        total_tracks = len(music_list)
        self.statusBar().showMessage(f"COMPLETE: Fetched {total_tracks} tracks. Processing...", 5000)
        artists_map, albums_map = self.process_music_list(music_list)
        self.save_collection_to_file(artists_map, albums_map)
        self.populate_trees(artists_map, albums_map)
        self.statusBar().showMessage(f"Finished. Loaded {len(artists_map)} artists and {len(albums_map)} albums.", 10000)
        self.start_button.setEnabled(True)
        self.start_button.setText("Refresh collection from device")

    def on_fetching_error(self, error_message):
        self.statusBar().showMessage(f"ERROR: {error_message}")
        self.start_button.setEnabled(True)
        self.start_button.setText("Refresh collection from device")

    def send_player_command(self, command):
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.statusBar().showMessage("ERROR: Please enter an IP address in Configuration.")
            return
        self.statusBar().showMessage(f"Sending command: {command}...")
        self.play_control_thread = PlayerControlThread(ip_address, command)
        self.play_control_thread.finished.connect(self.on_command_success)
        self.play_control_thread.error.connect(self.on_command_error)
        self.play_control_thread.start()

    def send_remote_key_command(self, key):
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.statusBar().showMessage("ERROR: Please enter an IP address in Configuration.")
            return
        self.statusBar().showMessage(f"Sending key: {key}...")
        self.remote_control_thread = RemoteControlThread(ip_address, key)
        self.remote_control_thread.finished.connect(self.on_command_success)
        self.remote_control_thread.error.connect(self.on_command_error)
        self.remote_control_thread.start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    app.setQuitOnLastWindowClosed(True) 
    
    window = EveRApp()
    window.show()
    sys.exit(app.exec())