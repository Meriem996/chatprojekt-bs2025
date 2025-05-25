"""
@file ipc.py
@brief Gemeinsame Queues für die Interprozesskommunikation (IPC) zwischen CLI, GUI, Netzwerk und Discovery.

@details
Dieses Modul stellt alle zentralen Queues für den Datenaustausch im BSRN-Chat zur Verfügung.
Sie werden von allen Hauptprozessen verwendet:

- UI (CLI/GUI): stellt Benutzeroberfläche bereit
- Netzwerkprozess: verarbeitet SLCP-Protokoll (JOIN, MSG, IMG usw.)
- Discoveryprozess: erkennt andere Benutzer im Netzwerk (WHOIS/IAM)

Die Queues ermöglichen eine strukturierte und sichere Übergabe von SLCP-Nachrichten,
Chatnachrichten, Bilderpfaden und Teilnehmerinformationen.
"""


from multiprocessing import Queue


# ================================================
# UI → Netzwerk: Von CLI/GUI zum Netzwerkprozess
# ================================================

## @brief Sende-Queue: Benutzeroberfläche sendet SLCP-Befehle (JOIN, MSG, IMG, LEAVE)
#  @details Nachrichten werden vom UI-Prozess erzeugt und im Netzwerkprozess verarbeitet.
#  Mögliche Formate:
#   - {"type": "broadcast", "data": "<SLCP-Nachricht>"}
#   - {"type": "direct_text", "to": "<Empfänger-Handle>", "data": "<SLCP-Nachricht>"}
#   - {"type": "direct_image", "to": "<Handle>", "data": "<SLCP-Nachricht>", "binary": <Bilddaten>}
queue_ui_to_net = Queue()


# ==================================================
# Netzwerk → UI: Netzwerkprozess liefert Daten an UI
# ==================================================

## @brief Empfangs-Queue: Der Netzwerkprozess schickt empfangene Daten an die Benutzeroberfläche.
#  @details Wird z. B. für eingehende Nachrichten, Bilder und Peer-Updates verwendet.
#  Formate:
#   - {"type": "text", "from": "<Sender-Handle>", "text": "<Nachricht>"}
#   - {"type": "image", "from": "<Sender-Handle>", "path": "<Pfad-zum-Bild>"}
#   - {"type": "peers_update", "peers": ["<handle1>", "<handle2>", ...]}
queue_net_to_ui = Queue()


# ================================================
# UI → Discovery: Sende WHOIS-Anfragen
# ================================================

## @brief Sende-Queue: UI gibt eine WHOIS-Anfrage weiter an den Discoveryprozess.
#  @details Wird verwendet, wenn der Benutzer z. B. „whois Bob“ ausführt.
#  Format:
#   - {"data": "<SLCP-Nachricht für WHOIS>"}
queue_ui_to_discovery = Queue()


# =====================================================
# Discovery → UI: Empfang von IAM-Antworten der Peers
# =====================================================

## @brief Empfangs-Queue: Discoveryprozess gibt IAM-Antworten an UI weiter.
#  @details Die UI kann damit IP-Adresse und Port eines anderen Nutzers darstellen.
#  Format:
#   - {"type": "iam", "handle": "<Benutzername>", "ip": "<IP-Adresse>", "port": <Portnummer>}
queue_discovery_to_ui = Queue()


queue_discovery_to_net = Queue()