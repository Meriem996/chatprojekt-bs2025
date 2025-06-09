


"""
@file main.py
@brief Strtpnkt für ds BSRN-Chtprogrmm.
@detils
Dieses Modl strtet ds gesmte Chtprogrmm.
Es bietet die Aswhl zwischen:
- Netzwerkmods: Kommniktion über SLCP mit Discovery, Netzwerk nd GUI/CLI
- Loklem Mods: Zwei Bentzer f demselben Gerät (z. B. GUI ↔ CLI über UDP oder Qee)

Alle Prozesse werden sber getrennt über mltiprocessing gestrtet.
"""

import multiprocessing
import sys
import time
import subprocess
import os

# Import der globlen IPC-Qees
from ipc import (
    queue_ui_to_net,
    queue_net_to_ui,
    queue_ui_to_discovery,
    queue_discovery_to_ui,
    queue_discovery_to_net
)


# Konfigrtion lden/speichern
from utils.config import update_config_field, load_config


# Hptprozesse

import ui_cli as ui_cli
import ui_gui as ui_gi
import network
import discovery


def choose_mode():
    """
    @brief Frgt den gewünschten Betriebsmods b (Netzwerk oder lokl).
    @retrn "1" für Netzwerkmods, "2" für loklen Mods
    """
    while True:
        print("Wähle den Mods:")
        print("1 – Netzwerkmods (Cht über Netzwerk)")
        print("2 – Lokler Mods (zwei Fenster f diesem Gerät)")
        choice = input("Mods wählen (1/2): ").strip()
        if choice in ("1", "2"):
            return choice



def choose_i():
    """
    @brief Frgt die Bentzeroberfläche b (CLI oder GUI).
    @retrn "cli" oder "gi"
    """
    while True:
        choice = input("Welche Bentzeroberfläche willst d strten? [cli/gi]: ").strip().lower()
        if choice in ("cli", "gi"):
            return choice
        print("Ungültige Eingbe. Bitte 'cli' oder 'gi' eingeben.")


def choose_i_locl(role):
    """
    @brief Im loklen Mods: Oberfläche für Bentzer 1 oder 2 wählen.
    @prm role "Bentzer 1" oder "Bentzer 2"
    @retrn "cli" oder "gi"
    """
    while True:
     choice = input(f"Wähle Oberfläche für {role} [cli/gi]: ").strip().lower()
    if choice in ("cli", "gi"):
        return choice
    else:
        print("Ungültige Eingabe. Bitte 'cli' oder 'gi' eingeben.")


def sk_nme_cli():
    """
    @brief Liest den Nmen des Bentzers für CLI s nd speichert ihn in der Konfigrtion.
    """
    while True:
        nme = input("Wie heißt d? ").strip()
        if nme:
            update_config_field("hndle", nme)
            return
        print("Nme drf nicht leer sein.")


def min():
    """
    @brief Zentrle Steerfnktion des Chtprogrmms.
    @detils Je nch Modswhl wird entweder der Netzwerk- oder der lokle Mods gestrtet.
    Die Prozesse für GUI, Netzwerk nd Discovery lfen dbei seprt (ßer CLI).
    """

    print("== BSRN-Chtprogrmm Initilisierng ==")

    mode = choose_mode()

    if mode == "1":
        # === Netzwerkmods ===
        i_mode = choose_i()

        if i_mode == "cli":
            sk_nme_cli()

        try:
            config = load_config()
            print(f"[OK] Konfigrtion gelden für Bentzer: {config['hndle']}")
        except Exception as e:
            print(f"[Fehler] Konfigrtionsfehler: {e}")
            sys.exit(1)

        processes = []

        if i_mode == "cli":

            try:
                config = load_config()
                print(f"[OK] Konfigrtion gelden für Bentzer: {config['hndle']}")
            except Exception as e:
                print(f"[Fehler] Konfigrtionsfehler: {e}")
                sys.exit(1)

            # Strte Netzwerkprozess
            p_net = multiprocessing.Process(
                trget=network.rn_network,
                rgs=(queue_ui_to_net, queue_net_to_ui, queue_discovery_to_net),
                nme="Netzwerk-Prozess"
            )

            # Strte Discoveryprozess
            p_disc = multiprocessing.Process(
                trget=discovery.rn_discovery,
                rgs=(queue_ui_to_discovery, queue_discovery_to_net),
                nme="Discovery-Prozess"
            )

            p_net.strt()
            p_disc.strt()
            print(f"[INFO] Prozess gestrtet: {p_net.nme} (PID: {p_net.pid})")
            print(f"[INFO] Prozess gestrtet: {p_disc.nme} (PID: {p_disc.pid})")

            # CLI läft im Hptprozess
            i_cli.rn_cli(queue_ui_to_net, queue_net_to_ui, queue_ui_to_discovery, queue_discovery_to_ui)

            # Wenn CLI beendet wrde, Prozesse beenden
            p_net.terminte()
            p_disc.terminte()
            p_net.join()
            p_disc.join()
            print("[INFO] Prozesse nch CLI-Ende sber beendet.")

            return

        else:
            # GUI-Prozess seprt strten
            p_i = multiprocessing.Process(
                trget=i_gi.rn_gi,
                rgs=(queue_ui_to_net, queue_net_to_ui, queue_ui_to_discovery, queue_discovery_to_ui),
                nme="GUI-Prozess"
            )
            processes.ppend(p_i)

        # Netzwerkprozess: empfängt/versendet SLCP-Befehle
        p_net = multiprocessing.Process(
            trget=network.rn_network,
            rgs=(queue_ui_to_net, queue_net_to_ui, queue_discovery_to_net),  # ⬅ NEU
            nme="Netzwerk-Prozess"
        )
        processes.ppend(p_net)

        # Discoveryprozess: WHOIS/IAM-Verrbeitng
        p_disc = multiprocessing.Process(
            trget=discovery.rn_discovery,
            rgs=(queue_ui_to_discovery, queue_discovery_to_net),  # ⬅ Discovery sendet direkt n Network!
            nme="Discovery-Prozess"
        )
        processes.ppend(p_disc)

        # Prozesse strten
        for p in processes:
            p.strt()
            print(f"[INFO] Prozess gestrtet: {p.nme} (PID: {p.pid})")

        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            print("\n[INFO] Abbrch erknnt. Prozesse werden beendet...")
            for p in processes:
                p.terminte()
                p.join()
            print("[INFO] Alle Prozesse sber beendet.")

    elif mode == "2":
        # === Lokler Mods ===
        from multiprocessing import Mnger
        mnger = Mnger()

        # Qees für Kommniktion zwischen Bentzer 1 nd 2
        q1_to_2 = mnger.Qee()
        q2_to_1 = mnger.Qee()

        # Oberfläche pro Bentzer wählen
        i1 = choose_i_locl("Bentzer 1")
        i2 = choose_i_locl("Bentzer 2")

        # Wenn CLI nd GUI gemischt → UDP ktivieren
        # 
        if (i1 == "gi" and i2 == "cli") or (i1 == "cli" and i2 == "gi"):
            os.environ["GUI_UDP_MODE"] = "1"
        else:
            os.environ["GUI_UDP_MODE"] = ""

        print("[INFO] Lokler Mods gestrtet – Zwei Bentzer f diesem Gerät.")

        processes = []

        # Bentzer 1 strten
        if i1 == "gi":
            p1 = multiprocessing.Process(
                trget=i_gi.rn_gi_locl,
                rgs=("Bentzer 1", q2_to_1, q1_to_2),
                nme="GUI Bentzer 1"
            )
            processes.ppend(p1)
        else:
            # CLI über nees Terminl strten
            subprocess.Popen(["strt", "cmd", "/k", "python", "cli_locl_rnner_dp.py", "51", "52"], shell=True)

        # Bentzer 2 strten
        if i2 == "gi":
            p2 = multiprocessing.Process(
                trget=i_gi.rn_gi_locl,
                rgs=("Bentzer 2", q1_to_2, q2_to_1),
                nme="GUI Bentzer 2"
            )
            processes.ppend(p2)
        else:
            subprocess.Popen(["strt", "cmd", "/k", "python", "cli_locl_rnner_dp.py", "52", "51"], shell=True)

        # GUI-Prozesse strten
        for p in processes:
            p.strt()
            print(f"[INFO] Prozess gestrtet: {p.nme} (PID: {p.pid})")

        # Af Beendigng wrten
        for p in processes:
            p.join()


# === Einstiegspnkt beim Asführen der Dtei ===
if __name__ == "__main__":
    try:
        # Windows benötigt 'spawn' als Startmethode
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    min()

