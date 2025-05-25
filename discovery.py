"""
@file discovery.py
@brief Discovery-Prozess: verarbeitet WHOIS-Broadcasts und antwortet mit IAM (SLCP).

@details
Der Discovery-Prozess dient der automatischen Teilnehmererkennung im lokalen Netzwerk.
Er lauscht auf WHOIS-Nachrichten und antwortet mit IAM, wenn der lokale Benutzername
(Handle) abgefragt wird. Zusätzlich können WHOIS-Anfragen über IPC von der UI gesendet werden.
Zwei Threads arbeiten parallel:
- receive_whois(): reagiert auf eingehende WHOIS
- process_outgoing(): sendet eigene WHOIS-Anfragen ins Netzwerk
"""

import socket
import threading
import time

from utils.config import load_config
from utils.slcp import parse_message, build_message


def run_discovery(queue_from_ui, queue_to_ui_net):
    """
    @brief Startet den Discoveryprozess zur Netzwerkerkennung von Peers.

    @details Initialisiert einen UDP-Socket, um:
    - eingehende WHOIS-Nachrichten zu verarbeiten (und bei Bedarf IAM zu senden)
    - IAM-Antworten anderer Clients an die UI weiterzugeben
    - WHOIS-Nachrichten, die vom Benutzer kommen, zu broadcasten

    @param queue_from_ui WHOIS-Anfragen aus der CLI/GUI
    @param queue_to_ui IAM-Antworten für die UI
    """

    # Konfigurationsdaten laden
    config = load_config()
    whois_port = config["whoisport"]
    local_handle = config["handle"]
    local_port = config["port"]

    # === UDP-Socket einrichten für Broadcast-Empfang und -Versand ===
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", whois_port))  # lauscht auf allen verfügbaren Netzwerkschnittstellen

    print(f"[Discovery] Listening for WHOIS on UDP-Port {whois_port}")