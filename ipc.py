"""
@file ipc.py
@brief Gemeinsame Queues für die Interprozesskommunikation (IPC) zwischen CLI, GUI, Netzwerk und Discovery.

@details
Dieses Modul stellt alle zentralen Queues für den Datenaustausch im BSRN-Chatprogramm bereit.
Sie dienen der Kommunikation zwischen den drei Hauptprozessen:

- Benutzeroberfläche (UI: CLI oder GUI)
- Netzwerkprozess (JOIN, MSG, IMG, LEAVE, IAM etc.)
- Discoveryprozess (WHOIS, IAM)

Durch diese Queues können SLCP-Kommandos, Textnachrichten, Bilder, Teilnehmerlisten und WHOIS-Antworten
sicher zwischen Prozessen übergeben werden.
"""

from multiprocessing import Queue


# ==============================================================
# UI → Netzwerk: Von CLI/GUI zur Verarbeitung im Netzwerkprozess
# ==============================================================

queue_ui_to_net = Queue()
"""
@brief Sende-Queue vom UI-Prozess an den Netzwerkprozess.

@details
Diese Queue überträgt SLCP-Befehle wie JOIN, MSG, IMG oder LEAVE.
Der Netzwerkprozess verarbeitet die übergebenen SLCP-Daten und führt passende Netzwerkaktionen aus.

Mögliche Datenformate:
- {"type": "broadcast", "data": "<SLCP-Nachricht>"}
- {"type": "direct_text", "to": "<Empfänger-Handle>", "data": "<SLCP-Nachricht>"}
- {"type": "direct_image", "to": "<Handle>", "data": "<SLCP-Nachricht>", "binary": <Binärdaten>}
"""


# =====================================================================
# Netzwerk → UI: Netzwerkprozess liefert empfangene Daten an das UI zurück
# =====================================================================

queue_net_to_ui = Queue()
"""
@brief Empfangs-Queue vom Netzwerkprozess an die Benutzeroberfläche.

@details
Diese Queue wird verwendet, um empfangene Textnachrichten, Bilder oder Peer-Listen
an das UI (CLI oder GUI) zu senden. Damit können eingehende Nachrichten dargestellt werden.

Beispielhafte Formate:
- {"type": "text", "from": "<Sender-Handle>", "text": "<Nachricht>"}
- {"type": "image", "from": "<Sender-Handle>", "path": "<Bildpfad>"}
- {"type": "peers_update", "peers": ["<handle1>", "<handle2>", ...]}
"""


# =============================================
# UI → Discovery: WHOIS-Anfrage auslösen
# =============================================

queue_ui_to_discovery = Queue()
"""
@brief Sende-Queue vom UI an den Discoveryprozess.

@details
Diese Queue transportiert WHOIS-Anfragen, z. B. wenn der Nutzer „whois Alice“ eingibt.

Format:
- {"data": "<SLCP-Nachricht für WHOIS>"}
"""


# ===================================================
# Discovery → UI: IAM-Antworten an Benutzeroberfläche
# ===================================================

queue_discovery_to_ui = Queue()
"""
@brief Empfangs-Queue für IAM-Antworten vom Discoveryprozess an die UI.

@details
Die IAM-Antwort enthält IP-Adresse und Port des gesuchten Peers,
z. B. als Reaktion auf eine WHOIS-Anfrage.

Format:
- {"type": "iam", "handle": "<Benutzername>", "ip": "<IP-Adresse>", "port": <Portnummer>}
"""


# ================================================
# Discovery → Netzwerk: Peers an Netzwerkprozess
# ================================================

queue_discovery_to_net = Queue()
"""
@brief Interne Queue vom Discoveryprozess zum Netzwerkprozess.

@details
Diese Queue überträgt Ergebnisse der WHOIS-Suche (z. B. neue Peer-Adressen) direkt
an den Netzwerkprozess, um Peer-Verbindungen aufzubauen.
"""
