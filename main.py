#!/usr/bin/env python3

import sys
import os
import requests
import zipfile
import subprocess
import threading
import json
import shutil
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QGroupBox, QRadioButton, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, QMetaObject, Q_ARG, Slot

# --- Configuration ---
PPLUS_API_URL = "https://api.github.com/repos/Project-Plus-Development-Team/Project-Plus-Dolphin/releases/latest"
REX_API_URL = "https://api.github.com/repos/the-outcaster/rex-for-linux/releases/latest"
ICON_PATH = Path.home() / "Pictures/pplus.png"

# --- Main Application Window ---
class PPlusLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project+/REX Updater")
        # Increased height slightly for the new button
        self.setGeometry(100, 100, 550, 640)

        self.base_install_dir = Path.home() / "Applications"
        self.install_dirs = {
            'project_plus': self.base_install_dir / 'ProjectPlus',
            'rex': self.base_install_dir / 'REX'
        }
        self.base_install_dir.mkdir(parents=True, exist_ok=True)
        ICON_PATH.parent.mkdir(exist_ok=True)

        self.game_mode = 'project_plus'

        self.latest_versions = {'project_plus': None, 'rex': None}
        self.installed_versions = {'project_plus': None, 'rex': None}
        self.appimage_paths = {'project_plus': None, 'rex': None}
        self.release_assets = {'project_plus': {}, 'rex': {}}

        self.has_7z = shutil.which('7z') is not None

        self.init_ui()
        self.check_local_versions()
        self.fetch_remote_versions()
        self.check_adapter_rate()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        location_box = QGroupBox("Base Install Location")
        location_layout = QVBoxLayout()
        self.location_label = QLabel(f"Current: {self.base_install_dir}")
        self.change_location_button = QPushButton("Change Location...")
        self.change_location_button.clicked.connect(self.change_install_location)
        location_layout.addWidget(self.location_label)
        location_layout.addWidget(self.change_location_button)
        location_box.setLayout(location_layout)
        main_layout.addWidget(location_box)

        game_box = QGroupBox("Select Game")
        game_layout = QVBoxLayout()

        self.project_plus_radio = QRadioButton("Project+")
        self.project_plus_radio.setChecked(True)
        self.project_plus_radio.toggled.connect(lambda: self.switch_game_mode('project_plus'))
        game_layout.addWidget(self.project_plus_radio)

        self.rex_radio = QRadioButton("REX")
        self.rex_radio.toggled.connect(lambda: self.switch_game_mode('rex'))
        self.rex_radio.setEnabled(self.has_7z)
        game_layout.addWidget(self.rex_radio)

        if not self.has_7z:
            warning_label = QLabel("REX requires '7z' (p7zip). Please install it and restart.")
            warning_label.setStyleSheet("color: 'orange';")
            game_layout.addWidget(warning_label)

        game_box.setLayout(game_layout)
        main_layout.addWidget(game_box)

        version_layout = QHBoxLayout()
        self.installed_version_label = QLabel("Installed: Not Found")
        self.latest_version_label = QLabel("Latest: Checking...")
        version_layout.addWidget(self.installed_version_label)
        version_layout.addWidget(self.latest_version_label)
        main_layout.addLayout(version_layout)

        action_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.launch_game)
        self.remove_button = QPushButton("Remove Installation")
        self.remove_button.clicked.connect(self.remove_installation)
        self.update_button = QPushButton("Download/Update")
        self.update_button.clicked.connect(self.start_download)
        action_layout.addWidget(self.play_button)
        action_layout.addWidget(self.remove_button)
        action_layout.addWidget(self.update_button)
        main_layout.addLayout(action_layout)

        self.progress_label = QLabel("Status: Idle")
        self.progress_label.setVisible(False)
        main_layout.addWidget(self.progress_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        self.speed_label = QLabel("")
        self.speed_label.setVisible(False)
        main_layout.addWidget(self.speed_label)

        tools_box = QGroupBox("System Tools")
        tools_layout = QVBoxLayout()

        self.hd_textures_button = QPushButton("Download HD Textures")
        self.hd_textures_button.clicked.connect(self.download_hd_textures)
        tools_layout.addWidget(self.hd_textures_button)

        shortcut_create_layout = QHBoxLayout()
        self.create_desktop_shortcut_button = QPushButton("Create Desktop Shortcut")
        self.create_desktop_shortcut_button.clicked.connect(lambda: self._create_shortcut('desktop'))
        self.create_app_shortcut_button = QPushButton("Create Applications Shortcut")
        self.create_app_shortcut_button.clicked.connect(lambda: self._create_shortcut('applications'))
        shortcut_create_layout.addWidget(self.create_desktop_shortcut_button)
        shortcut_create_layout.addWidget(self.create_app_shortcut_button)
        tools_layout.addLayout(shortcut_create_layout)

        shortcut_remove_layout = QHBoxLayout()
        self.remove_desktop_shortcut_button = QPushButton("Remove Desktop Shortcut")
        self.remove_desktop_shortcut_button.clicked.connect(lambda: self._remove_shortcut('desktop'))
        self.remove_app_shortcut_button = QPushButton("Remove Applications Shortcut")
        self.remove_app_shortcut_button.clicked.connect(lambda: self._remove_shortcut('applications'))
        shortcut_remove_layout.addWidget(self.remove_desktop_shortcut_button)
        shortcut_remove_layout.addWidget(self.remove_app_shortcut_button)
        tools_layout.addLayout(shortcut_remove_layout)

        adapter_layout = QHBoxLayout()
        self.adapter_rate_label = QLabel("GC Adapter Poll Rate: Unknown")
        self.overclock_button = QPushButton("Overclock Adapter")
        self.overclock_button.setVisible(False)
        self.overclock_button.clicked.connect(self.overclock_adapter)
        adapter_layout.addWidget(self.adapter_rate_label)
        adapter_layout.addWidget(self.overclock_button)
        tools_layout.addLayout(adapter_layout)
        tools_box.setLayout(tools_layout)
        main_layout.addWidget(tools_box)

        # **NEW: About and Changelog Buttons**
        bottom_button_layout = QHBoxLayout()
        self.changelog_button = QPushButton("View Changelog")
        self.changelog_button.clicked.connect(self.view_changelog)
        self.about_button = QPushButton("About")
        self.about_button.clicked.connect(self.show_about_dialog)
        bottom_button_layout.addWidget(self.changelog_button)
        bottom_button_layout.addWidget(self.about_button)
        main_layout.addLayout(bottom_button_layout)

        self.update_ui_for_mode()

    @Slot(str)
    def switch_game_mode(self, mode):
        self.game_mode = mode
        self.check_local_versions()

    @Slot()
    def change_install_location(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Base Install Location", str(self.base_install_dir))
        if new_dir:
            self.base_install_dir = Path(new_dir)
            self.install_dirs['project_plus'] = self.base_install_dir / 'ProjectPlus'
            self.install_dirs['rex'] = self.base_install_dir / 'REX'
            self.location_label.setText(f"Current: {self.base_install_dir}")
            self.check_local_versions()

    def _get_shortcut_path(self, location):
        desktop_filename = f"project-plus-{self.game_mode}.desktop"
        if location == 'desktop':
            return Path.home() / "Desktop" / desktop_filename
        else:
            return Path.home() / ".local/share/applications" / desktop_filename

    @Slot()
    def update_ui_for_mode(self):
        asset_info = self.release_assets.get(self.game_mode, {})
        total_size_gb = asset_info.get('total_size', 0) / (1024 * 1024 * 1024)

        installed_v = self.installed_versions[self.game_mode]
        latest_v = self.latest_versions[self.game_mode]

        self.installed_version_label.setText(f"Installed: {installed_v or 'Not Found'}")
        self.latest_version_label.setText(f"Latest: {latest_v or 'Checking...'}")

        is_installed = bool(installed_v and self.install_dirs[self.game_mode].exists())
        is_playable = bool(is_installed and self.appimage_paths[self.game_mode])
        hd_ready = bool(is_installed and 'hd_textures' in self.release_assets[self.game_mode])

        self.play_button.setEnabled(is_playable)
        self.remove_button.setEnabled(is_installed)
        self.create_desktop_shortcut_button.setEnabled(is_playable)
        self.create_app_shortcut_button.setEnabled(is_playable)

        self.hd_textures_button.setVisible(True)
        self.hd_textures_button.setEnabled(hd_ready)

        self.remove_desktop_shortcut_button.setEnabled(self._get_shortcut_path('desktop').exists())
        self.remove_app_shortcut_button.setEnabled(self._get_shortcut_path('applications').exists())

        if is_playable:
            self.play_button.setText(f"Play {installed_v}")
        else:
            self.play_button.setText("Play")

        if latest_v and installed_v != latest_v:
            self.update_button.setText(f"Update to {latest_v} (~{total_size_gb:.1f} GB)")
            self.update_button.setEnabled(True)
        elif not installed_v and latest_v:
            self.update_button.setText(f"Download {latest_v} (~{total_size_gb:.1f} GB)")
            self.update_button.setEnabled(True)
        else:
            self.update_button.setText("Up to Date")
            self.update_button.setEnabled(False)

    @Slot()
    def check_local_versions(self):
        for mode, directory in self.install_dirs.items():
            version_file = directory / ".version"
            if directory.exists() and version_file.exists():
                self.installed_versions[mode] = version_file.read_text().strip()
                appimages = list(directory.glob('**/*.AppImage'))
                self.appimage_paths[mode] = appimages[0] if appimages else None
            else:
                self.installed_versions[mode] = None
                self.appimage_paths[mode] = None
        self.update_ui_for_mode()

    def fetch_remote_versions(self):
        threading.Thread(target=self._fetch_remote_version_worker, daemon=True).start()

    def _fetch_remote_version_worker(self):
        try:
            resp_pp = requests.get(PPLUS_API_URL)
            resp_pp.raise_for_status()
            data_pp = resp_pp.json()
            self.latest_versions['project_plus'] = data_pp['tag_name']
            total_size_pp = 0
            for asset in data_pp['assets']:
                if asset['name'].endswith(".AppImage.zip"):
                    self.release_assets['project_plus']['appimage'] = asset
                    total_size_pp += asset['size']
                elif asset['name'].endswith(".HD.Textures.zip"):
                    self.release_assets['project_plus']['hd_textures'] = asset
            self.release_assets['project_plus']['total_size'] = total_size_pp

            if self.has_7z:
                resp_rex = requests.get(REX_API_URL)
                resp_rex.raise_for_status()
                data_rex = resp_rex.json()
                self.latest_versions['rex'] = data_rex['tag_name']

                rex_parts = [a for a in data_rex['assets'] if ".zip." in a['name']]
                self.release_assets['rex']['parts'] = sorted(rex_parts, key=lambda x: x['name'])
                self.release_assets['rex']['total_size'] = sum(a['size'] for a in rex_parts)

                for asset in data_rex['assets']:
                    if asset['name'] == "rex-hd-textures.zip":
                        self.release_assets['rex']['hd_textures'] = asset
                        break

        except requests.RequestException as e:
            QMetaObject.invokeMethod(self, 'show_error_message', Qt.QueuedConnection, Q_ARG(str, f"Could not fetch latest versions: {e}"))
        QMetaObject.invokeMethod(self, 'update_ui_for_mode', Qt.QueuedConnection)

    def remove_installation(self):
        current_dir = self.install_dirs[self.game_mode]
        reply = QMessageBox.question(self, 'Confirm Removal',
            f"Are you sure you want to permanently delete this installation?\n\nThis will remove all files in:\n{current_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if current_dir.exists(): shutil.rmtree(current_dir)
                desktop_filename = f"project-plus-{self.game_mode}.desktop"
                (Path.home() / "Desktop" / desktop_filename).unlink(missing_ok=True)
                (Path.home() / ".local/share/applications" / desktop_filename).unlink(missing_ok=True)
            except (IOError, OSError) as e:
                self.show_error_message(f"Could not remove installation: {e}")
            finally:
                self.check_local_versions()

    def launch_game(self):
        appimage_path = self.appimage_paths[self.game_mode]
        if appimage_path and appimage_path.exists():
            appimage_path.chmod(0o755)
            subprocess.Popen([appimage_path], cwd=appimage_path.parent)
        else:
            self.show_error_message("AppImage not found! Please download it first.")

    def start_download(self):
        self.progress_bar.setValue(0)
        for widget in [self.progress_bar, self.progress_label, self.speed_label]:
            widget.setVisible(True)
        self.update_button.setEnabled(False)
        threading.Thread(target=self._download_and_extract, daemon=True).start()

    def _download_asset(self, url, filename, progress_share, start_progress):
        temp_download_path = self.base_install_dir / filename
        QMetaObject.invokeMethod(self.progress_label, 'setText', Qt.QueuedConnection, Q_ARG(str, f"Downloading: {filename}"))
        start_time = time.time()
        last_update_time = start_time

        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            downloaded_size = 0
            with open(temp_download_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    current_time = time.time()
                    if total_size > 0:
                        progress = int(start_progress + (downloaded_size / total_size) * progress_share)
                        QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, progress))
                    if current_time - last_update_time > 0.5:
                        speed = downloaded_size / (current_time - start_time) / (1024*1024)
                        QMetaObject.invokeMethod(self.speed_label, 'setText', Qt.QueuedConnection, Q_ARG(str, f"{speed:.2f} MB/s"))
                        last_update_time = current_time

        QMetaObject.invokeMethod(self.speed_label, 'setText', Qt.QueuedConnection, Q_ARG(str, ""))
        return temp_download_path

    def _download_and_extract(self):
        current_dir = self.install_dirs[self.game_mode]
        current_dir.mkdir(parents=True, exist_ok=True)

        try:
            if self.game_mode == 'project_plus':
                self._extract_project_plus(current_dir)
            elif self.game_mode == 'rex':
                self._extract_rex(current_dir)

            version_tag = self.latest_versions[self.game_mode]
            with open(current_dir / ".version", "w") as f:
                f.write(version_tag)

        except Exception as e:
            QMetaObject.invokeMethod(self, 'show_error_message', Qt.QueuedConnection, Q_ARG(str, f"Operation failed: {e}"))
        finally:
            for widget in [self.progress_bar, self.progress_label, self.speed_label]:
                QMetaObject.invokeMethod(widget, 'setVisible', Qt.QueuedConnection, Q_ARG(bool, False))
            self.check_local_versions()

    def _extract_project_plus(self, target_dir):
        asset_to_download = self.release_assets['project_plus'].get('appimage')
        if not asset_to_download:
            raise ValueError("Could not find P+ AppImage asset.")

        file_path = self._download_asset(
            asset_to_download['browser_download_url'],
            asset_to_download['name'], 80, 0
        )

        QMetaObject.invokeMethod(self.progress_label, 'setText', Qt.QueuedConnection, Q_ARG(str, f"Extracting: {file_path.name}"))
        QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, 85))

        with zipfile.ZipFile(file_path, 'r') as zipf:
            zipf.extractall(path=target_dir)

        QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, 100))
        file_path.unlink()

    def _extract_rex(self, target_dir):
        parts_to_download = self.release_assets['rex'].get('parts')
        if not parts_to_download:
            raise ValueError("Could not find REX assets.")

        total_parts = len(parts_to_download)
        downloaded_part_paths = []

        for i, asset in enumerate(parts_to_download):
            progress_share = (80 / total_parts)
            start_progress = i * progress_share
            path = self._download_asset(
                asset['browser_download_url'],
                asset['name'], progress_share, start_progress
            )
            downloaded_part_paths.append(path)

        QMetaObject.invokeMethod(self.progress_label, 'setText', Qt.QueuedConnection, Q_ARG(str, "Extracting REX archive... (this may take a while)"))
        QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, 85))

        first_part_path = downloaded_part_paths[0]

        try:
            subprocess.run(
                ["7z", "x", str(first_part_path), f"-o{target_dir}", "-y"],
                check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"7z extraction failed: {e.stderr}")

        QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, 100))

        for part_path in downloaded_part_paths:
            part_path.unlink()

    # --- HD Texture Helper Functions ---

    def _get_hd_texture_base_path(self):
        if not self.appimage_paths[self.game_mode]:
            return None

        appimage_file = self.appimage_paths[self.game_mode]
        if self.game_mode == 'project_plus':
            return self.install_dirs['project_plus'] / "Project-Plus-Dolphin.AppImage.home/.local/share/project-plus-dolphin/"
        elif self.game_mode == 'rex':
            return appimage_file.parent / "Project-Plus-Dolphin.AppImage.home/.local/share/project-plus-dolphin/"
        return None

    def _check_hd_textures_exist(self):
        base_path = self._get_hd_texture_base_path()
        if not base_path:
            return False

        texture_path = base_path / "Load/Textures/RSBE01"
        return texture_path.exists() and any(texture_path.iterdir())

    @Slot()
    def download_hd_textures(self):
        asset = self.release_assets[self.game_mode].get('hd_textures')
        if not asset:
            self.show_error_message(f"Could not find HD Texture asset for {self.game_mode}.")
            return

        if not self.appimage_paths[self.game_mode]:
            self.show_error_message("Please install the main game before downloading textures.")
            return

        if self._check_hd_textures_exist():
            reply = QMessageBox.question(self, 'Textures Already Exist',
                "HD textures for this game appear to be installed. Do you want to download and overwrite them anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.No:
                return

        self.progress_bar.setValue(0)
        for widget in [self.progress_bar, self.progress_label, self.speed_label]:
            widget.setVisible(True)
        self.hd_textures_button.setEnabled(False)

        threading.Thread(target=self._hd_texture_worker, args=(asset,), daemon=True).start()

    def _hd_texture_worker(self, asset):
        try:
            base_extract_path = self._get_hd_texture_base_path()
            if not base_extract_path:
                raise Exception("Could not determine texture installation path.")

            if self.game_mode == 'project_plus':
                extract_path = base_extract_path / "Load/Textures/"
                TEXTURE_GAME_ID = "RSBE01"
            elif self.game_mode == 'rex':
                extract_path = base_extract_path
                TEXTURE_GAME_ID = "RSBE01"

            extract_path.mkdir(parents=True, exist_ok=True)

            file_path = self._download_asset(
                asset['browser_download_url'],
                asset['name'], 80, 0
            )

            QMetaObject.invokeMethod(self.progress_label, 'setText', Qt.QueuedConnection, Q_ARG(str, f"Extracting: {file_path.name}"))
            QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, 85))

            with zipfile.ZipFile(file_path, 'r') as zipf:
                if self.game_mode == 'rex':
                    zipf.extractall(path=extract_path)
                else:
                    for member in zipf.infolist():
                        if member.is_dir(): continue
                        try:
                            path_parts = member.filename.split('/')
                            id_index = path_parts.index(TEXTURE_GAME_ID)
                            new_relative_path = Path(*path_parts[id_index:])
                        except ValueError: continue

                        final_dest_path = extract_path / new_relative_path
                        final_dest_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(final_dest_path, 'wb') as f:
                            f.write(zipf.read(member))

            QMetaObject.invokeMethod(self.progress_bar, 'setValue', Qt.QueuedConnection, Q_ARG(int, 100))
            file_path.unlink()

            QMetaObject.invokeMethod(self, 'show_hd_texture_message', Qt.QueuedConnection, Q_ARG(str, str(base_extract_path)))

        except Exception as e:
            QMetaObject.invokeMethod(self, 'show_error_message', Qt.QueuedConnection, Q_ARG(str, f"HD Texture download failed: {e}"))
        finally:
            for widget in [self.progress_bar, self.progress_label, self.speed_label]:
                QMetaObject.invokeMethod(widget, 'setVisible', Qt.QueuedConnection, Q_ARG(bool, False))
            self.hd_textures_button.setEnabled(True)
            self.update_ui_for_mode()

    def check_adapter_rate(self):
        rate_file = Path("/sys/module/gcadapter_oc/parameters/rate")
        display_text = "GC Adapter Poll Rate: "
        try:
            if not rate_file.exists(): raise FileNotFoundError("gcadapter_oc module not found.")
            rate_value = int(rate_file.read_text().strip())
            rate_map = {1: "1,000 Hz", 2: "500 Hz", 4: "250 Hz", 8: "125 Hz"}
            display_text += rate_map.get(rate_value, f"Unknown ({rate_value})")
            if rate_value != 1: self.overclock_button.setVisible(True)
        except Exception as e:
            display_text += "Not Found"; self.overclock_button.setVisible(True)
        self.adapter_rate_label.setText(display_text)

    def overclock_adapter(self):
        command = "curl -L https://raw.githubusercontent.com/the-outcaster/gcadapter-oc-kmod-deck/main/install_gcadapter-oc-kmod.sh | sh"
        QMessageBox.information(self, "Overclocking Adapter", f"This will execute a script to install/update the overclocked adapter module.\n\nCommand:\n{command}\n\nYou may be prompted for your administrator password.")
        try:
            subprocess.run(['gnome-terminal', '--', 'bash', '-c', f"{command}; echo 'Press Enter to close...'; read"])
        except FileNotFoundError:
             try: subprocess.run(['konsole', '-e', 'bash', '-c', f"{command}; echo 'Press Enter to close...'; read"])
             except FileNotFoundError: self.show_error_message("Could not find gnome-terminal or konsole.")
        QMessageBox.information(self, "Restart Recommended", "The overclock script has finished. Please restart the launcher to see the updated adapter rate.")

    @Slot(str)
    def _remove_shortcut(self, location):
        path_to_remove = self._get_shortcut_path(location)
        if path_to_remove.exists():
            try:
                path_to_remove.unlink()
                QMessageBox.information(self, "Success", f"Shortcut removed from {location}.")
                self.update_ui_for_mode()
            except IOError as e:
                self.show_error_message(f"Could not remove shortcut: {e}")
        else:
            self.show_error_message("Shortcut not found.")
            self.update_ui_for_mode()

    def _create_shortcut(self, location):
        appimage_path = self.appimage_paths[self.game_mode]
        if not (appimage_path and appimage_path.exists()):
            self.show_error_message("Cannot create shortcut: AppImage not found."); return
        if not ICON_PATH.exists():
            try:
                icon_data = requests.get("https://cdn2.steamgriddb.com/icon/8d9a15b55c2ac9becb69a52624396966.png").content
                with open(ICON_PATH, 'wb') as f: f.write(icon_data)
            except requests.RequestException as e:
                self.show_error_message(f"Failed to download icon: {e}"); return

        shortcut_name = "Project+" if self.game_mode == 'project_plus' else "REX"
        save_path = self._get_shortcut_path(location)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        desktop_content = f"""[Desktop Entry]
        Version=1.0
        Name={shortcut_name}
        Comment=A Super Smash Bros. Brawl Mod
        Exec="{appimage_path}"
        Icon={ICON_PATH}
        Terminal=false
        Type=Application
        Categories=Game;
        """

        try:
            save_path.write_text(desktop_content)
            save_path.chmod(0o755)
            QMessageBox.information(self, "Success", f"Shortcut created at:\n{save_path}")
            self.update_ui_for_mode()
        except IOError as e: self.show_error_message(f"Failed to write shortcut file: {e}")

    def view_changelog(self):
        api_url = PPLUS_API_URL if self.game_mode == 'project_plus' else REX_API_URL
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            changelog, version = data.get('body', 'No changelog found.'), data.get('name', 'Latest Release')
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"Changelog for {version}")
            msg_box.setText(changelog.replace('\r\n', '<br/>'))
            msg_box.setTextFormat(Qt.RichText)
            msg_box.exec()
        except requests.RequestException as e: self.show_error_message(f"Could not fetch changelog: {e}")

    @Slot()
    def show_about_dialog(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About Project+/REX Updater")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(
            "Created by <b>Linux Gaming Central</b>"
            "<br><br>"
            "<a href='https://linuxgamingcentral.org/'>https://linuxgamingcentral.org/</a>"
        )
        msg_box.exec()

    @Slot(str)
    def show_hd_texture_message(self, base_path_str):
        full_texture_path = Path(base_path_str) / "Load/Textures/RSBE01"
        QMessageBox.information(self, "HD Textures Installed",
            f"The HD Textures have been successfully downloaded and extracted to:\n\n"
            f"{full_texture_path}\n\n"
            "To enable them, open the game (Dolphin), go to **Graphics > Advanced** and check **'Load Custom Textures'**.")

    @Slot(str)
    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PPlusLauncher()
    window.show()
    sys.exit(app.exec())
