# Project+ / REX Updater for Steam Deck/Linux
GUI application for Steam Deck/Linux that downloads, updates, and manages [Project+](https://projectplusgame.com/) and [REX](https://www.rexbuild.site/). Easily switch between P+ or REX builds, download/install HD textures for each, support for GameCube controller adapter overclocking (based on [this script](https://github.com/the-outcaster/gcadapter-oc-kmod-deck)), application shortcuts, and more!

![Screenshot](https://i.imgur.com/Z8PCauk.png)

Unofficial REX builds for Linux are hosted [here](https://github.com/the-outcaster/rex-for-linux).

## Usage
This application is packaged as a standalone executable. You may need to install `p7zip` in order to download/extract REX. Go to the [Releases](https://github.com/the-outcaster/projectplus-updater/releases) page of this repository and download the latest `Project+_REX_Updater-<version-number>` file. You may have to mark the file as an executable in order to run it.

## Development
If you want to develop for this project, you may need to create a Python 3.13 virtual environment first; if you have Python 3.14 or later installed on your system, `PySide6` won't work with newer versions.

```
git clone https://github.com/the-outcaster/projectplus-updater.git
cd projectplus-updater
python3.13 -m venv venv
source venv/bin/activate
pip install PySide6 requests pyinstaller
python main.py
```

When finished, you can build the executable with `build.sh`. The executable will be stored in `~/Applications`.
