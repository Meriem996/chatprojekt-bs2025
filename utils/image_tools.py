"""
@file image_tools.py
@brief Hilfsfunktionen zum Speichern, Laden und Anzeigen von Bilddateien im SLCP-Kontext.

@details
Dieses Modul wird von der GUI (und teils vom Netzwerkprozess) verwendet, um:
- Bilder zu speichern (empfangene Dateien)
- Bildgrößen zu ermitteln (für SLCP-IMG-Header)
- Binärdaten aus Dateien zu laden (vor dem Versand)
- empfangene Bilder mit dem Standardprogramm zu öffnen

Die Funktionen sind plattformunabhängig (Windows, macOS, Linux) und
einheitlich in das BSRN-Chatprojekt eingebunden.
"""

import os
from datetime import datetime
from pathlib import Path
import platform
import subprocess


def save_image(data: bytes, target_dir: str, sender_handle: str) -> str:
    """
    @brief Speichert ein empfangenes Bild mit Zeitstempel und Absendername.
    @param data Binärdaten des Bildes
    @param target_dir Zielverzeichnis für das Bild
    @param sender_handle Handle des Absenders (zur Kennzeichnung der Datei)
    @return Vollständiger Pfad zur gespeicherten Bilddatei
    """

    # Zeitstempel für Dateinamen erzeugen
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{sender_handle}_{timestamp}.jpg"

    # Zielverzeichnis erstellen (rekursiv, falls nötig)
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    full_path = os.path.join(target_dir, filename)

    # Bild binär schreiben
    with open(full_path, 'wb') as f:
        f.write(data)

    # Rückgabe des vollständigen Pfads
    return full_path


def get_image_size(filepath: str) -> int:
    """
    @brief Gibt die Größe einer Bilddatei in Bytes zurück.
    @param filepath Pfad zur Bilddatei
    @return Größe in Bytes
    @raises FileNotFoundError Wenn die Datei nicht existiert
    """

    # Existenz der Datei prüfen
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")

    # Größe berechnen
    return os.path.getsize(filepath)


def read_image_bytes(filepath: str) -> bytes:
    """
    @brief Liest eine Bilddatei vollständig in den Arbeitsspeicher.
    @param filepath Pfad zur Bilddatei
    @return Binärdaten der Datei (bytes)
    @raises FileNotFoundError Wenn Datei nicht existiert
    """

    # Existenz prüfen
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Datei nicht gefunden: {filepath}")

    # Datei als Binärdaten lesen
    with open(filepath, 'rb') as f:
        return f.read()


def open_image(filepath: str):
    """
    @brief Öffnet ein Bild mit dem Standard-Viewer des Betriebssystems.
    @param filepath Pfad zur Bilddatei
    @details Der Öffnungsvorgang ist betriebssystemabhängig:
        - macOS: open
        - Windows: os.startfile
        - Linux: xdg-open
    """

    # Prüfen, ob Datei existiert
    if not os.path.exists(filepath):
        print(f"[Bildanzeige] Datei nicht gefunden: {filepath}")
        return

    # Betriebssystem bestimmen
    system = platform.system()

    try:
        # macOS: öffnet mit "open"
        if system == "Darwin":
            subprocess.run(["open", filepath])

        # Windows: öffnet mit Standardprogramm
        elif system == "Windows":
            os.startfile(filepath)

        # Linux: nutzt xdg-open
        else:
            subprocess.run(["xdg-open", filepath])

    except Exception as e:
        print(f"[Bildanzeige] Fehler beim Öffnen des Bildes: {e}")