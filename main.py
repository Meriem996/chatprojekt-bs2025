"""
@file main.py
@brief Startpunkt für das BSRN-Chatprogramm.
@details
Dieses Modul startet das gesamte Chatprogramm.
Es bietet die Auswahl zwischen:
- Netzwerkmodus: Kommunikation über SLCP mit Discovery, Netzwerk und GUI/CLI
- Lokalem Modus: Zwei Benutzer auf demselben Gerät (z. B. GUI ↔ CLI über UDP oder Queue)

Alle Prozesse werden sauber getrennt über multiprocessing gestartet.
"""

import multiprocessing
import sys
import time
import subprocess
import os

# Import der globalen IPC-Queues
from ipc import (
    queue_ui_to_net,
    queue_net_to_ui,
    queue_ui_to_discovery,
    queue_discovery_to_ui,
    queue_discovery_to_net
)

# Konfiguration laden/speichern
from utils.config import update_config_field, load_config

# Hauptprozesse
import ui_cli
import ui_gui
import network
import discovery


def choose_mode():
    """
    @brief Fragt den gewünschten Betriebsmodus ab (Netzwerk oder lokal).
    @return "1" für Netzwerkmodus, "2" für lokalen Modusa
    """
    while True:
        print("Wähle den Modus:")
        print("1 – Netzwerkmodus (Chat über Netzwerk)")
        print("2 – Lokaler Modus (zwei Fenster auf diesem Gerät)")
        choice = input("Modus wählen (1/2): ").strip()
        if choice in ("1", "2"):
            return choice


def choose_ui():
    """
    @brief Fragt die Benutzeroberfläche ab (CLI oder GUI).
    @return "cli" oder "gui"
    """
    while True:
        choice = input("Welche Benutzeroberfläche willst du starten? [cli/gui]: ").strip().lower()
        if choice in ("cli", "gui"):
            return choice
        print("Ungültige Eingabe. Bitte 'cli' oder 'gui' eingeben.")


def choose_ui_local(role):
