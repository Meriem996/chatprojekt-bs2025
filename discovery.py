<<<<<<< HEAD
"""
@file discovery.py
@brief Discovery-Komponente für SLCP-Chat.

@details
Diese Datei enthält den Discovery-Prozess zur Erkennung anderer Chat-Clients im lokalen Netzwerk.
Sie verarbeitet WHOIS-Anfragen und antwortet mit IAM-Nachrichten.
Zwei Hintergrund-Threads werden verwendet:
- receive_whois(): verarbeitet eingehende WHOIS/IAM
- process_outgoing(): sendet WHOIS-Broadcasts
"""
import socket
import threading
import time
from utils.slcp import parse_message,build_message


"""
@file discovery.py
@brief Discovery-Komponente für SLCP-Chat.

@details
Diese Datei enthält den Discovery-Prozess zur Erkennung anderer Chat-Clients im lokalen Netzwerk.
Sie verarbeitet WHOIS-Anfragen und antwortet mit IAM-Nachrichten.
Zwei Hintergrund-Threads werden verwendet:
- receive_whois(): verarbeitet eingehende WHOIS/IAM
- process_outgoing(): sendet WHOIS-Broadcasts
"""
import socket
import threading
import time
from utils.slcp import parse_message,build_message
def run_discovery(queue_from_ui, queue_to_ui_net, config):
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
    whois_port = config["whoisport"]
    local_handle = config["handle"]
    local_port = config["port"]
>>>>>>> 0ab78cc (Discovery-Modul:  ergänzt)
