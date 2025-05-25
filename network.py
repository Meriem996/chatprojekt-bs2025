"""
@file network.py
@brief Netzwerkprozess: verarbeitet SLCP-Nachrichten, versendet/empfängt MSG & IMG, verwaltet Kontakte.

@details
Dieser Prozess ist einer der drei Hauptprozesse des BSRN-Chatprogramms.
Er verarbeitet alle Netzwerkaktionen über das Simple Local Chat Protocol (SLCP).
Er:
- lauscht auf UDP (JOIN, LEAVE, MSG, IMG-Steuerbefehl)
- empfängt Daten über TCP (Bilder und lange Nachrichten)
- sendet Nachrichten direkt per UDP/TCP
- pflegt eine Liste aller bekannten Teilnehmer ("peers")
- leitet Nachrichten und Updates an die UI weiter
"""

import socket
import threading
import time
import traceback

from utils.config import load_config, get_config_value
from utils.slcp import build_message, parse_message
from utils.image_tools import save_image

# Lokale Peer-Datenbank: handle → (IP, Port)
# Wird durch JOIN, WHOIS/IAM oder eingehende Nachrichten gepflegt
peers = {}


def get_broadcast_address():
    """
    @brief Ermittelt die passende Broadcast-Adresse für das lokale Subnetz.
    @details Wandelt z. B. 192.168.1.24 → 192.168.1.255 um.
             Fallback: 255.255.255.255 bei Fehlern.
    @return Broadcast-IP als String
    """
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        base = '.'.join(ip.split('.')[:-1])
        return f"{base}.255"
    except Exception:
        return '255.255.255.255'


def run_network(queue_from_ui, queue_to_ui, queue_from_discovery):
    """
    @brief Startet den Netzwerkprozess: SLCP-Verarbeitung, TCP/UDP-Kommunikation und Peer-Verwaltung.
    @param queue_from_ui Nachrichten von der UI (z. B. MSG, IMG, JOIN etc.)
    @param queue_to_ui Nachrichten an die UI (empfangene Texte, Bilder, Peer-Updates)
    """

    # Konfiguration laden
    config = load_config()
    whois_port = config["whoisport"]  # WHOIS-Port laden
    handle = config["handle"]
    listen_port = config["port"]
    image_dir = config["imagepath"]

    # === UDP-Socket vorbereiten (für SLCP-Befehle über UDP) ===
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("", listen_port))

    # === TCP-Socket für eingehende Verbindungen (z. B. Bilder) ===
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind(("", listen_port))
    tcp_socket.listen(10)

    # === Zusätzlicher UDP-Socket für WHOIS/IAM (Port z. B. 5001) ===
    whois_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    whois_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    whois_socket.bind(("", whois_port))

    print(f"[Netzwerk] Lausche auf Port {listen_port} (UDP & TCP)")