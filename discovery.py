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
import traceback 
from utils.slcp import parse_message, build_message
from utils.config import get_config_value  
from utils.network_utils import detect_broadcast_address
from queue import Empty

def run_discovery(queue_from_ui, queue_to_ui_net, config, receive_only=False):
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
    autoreply = get_config_value("autoreply")
    local_port = config["port"]

    joined = False  # ← lokale Variable für JOIN-Zustand

    # === UDP-Socket einrichten für Broadcast-Empfang und -Versand ===
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
       udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  
    except AttributeError:
        pass  
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", whois_port))  # lauscht auf allen verfügbaren Netzwerkschnittstellen

    print(f"[Discovery] Listening for WHOIS on UDP-Port {whois_port}")

    def receive_whois():
        """
        @brief Thread zum Empfang und zur Verarbeitung eingehender WHOIS- oder IAM-Nachrichten.
        @details
        - Prüft, ob eine WHOIS-Anfrage dem eigenen Handle entspricht → antwortet mit IAM
        - Erkennt eingehende IAM-Nachrichten und leitet sie zur Anzeige an die UI weiter
        """
        nonlocal joined
        while True:
            try:
                # WHOIS/IAM-Nachricht empfangen
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode("utf-8").strip()
                parsed = parse_message(message)

                # === WHOIS erhalten → prüfen, ob es an uns gerichtet ist ===
                if parsed["command"] == "WHOIS" and parsed["params"][0] == local_handle:
                    if not joined:
                        print("[Discovery] WHOIS empfangen, aber du bist nicht joined – keine IAM-Antwort.")
                         # ==== Auto-Reply senden ====
                        try:
                            target_port = int(parsed["params"][1])
                            reply_text = get_config_value("autoreply")
                            if reply_text:
                               reply_msg = build_message("MSG", local_handle, "[autoreply] " + autoreply)
                               udp_socket.sendto(reply_msg.encode("utf-8"), (addr[0], target_port))
                               print(f"[Discovery] Auto-Reply gesendet an {addr[0]}:{target_port}")
                        except (IndexError, ValueError):
                            print("[Discovery-Fehler] WHOIS enthält keinen gültigen Ziel-Port für Auto-Reply.")
                        except Exception as e:
                            print(f"[Discovery-Fehler] Fehler beim Auto-Reply: {e}")

                        continue  # weiterhin keine IAM senden
                    
                    try:
                        target_port = int(parsed["params"][1])  # ← der Port des Fragenden
                    except (IndexError, ValueError):
                        print("[Discovery-Fehler] WHOIS enthält keinen gültigen Ziel-Port")
                        continue

                    iam_msg = build_message("IAM", local_handle, get_own_ip(), local_port)

                    # IAM jetzt **immer über Broadcast senden**
                    broadcast_ip = detect_broadcast_address()
                    udp_socket.sendto(iam_msg.encode("utf-8"), (broadcast_ip, whois_port))

                    print(f"[Discovery] WHOIS erhalten von {addr}, IAM als Broadcast gesendet an {broadcast_ip}:{whois_port}")


                # === IAM erhalten → weiterleiten an UI ===
                elif parsed["command"] == "IAM":
                    handle, ip, port = parsed["params"]

                    queue_to_ui_net.put({
                        "type": "iam",
                        "handle": handle,
                        "ip": ip,
                        "port": int(port)
                    })

            except Exception as e:
                print(f"[Discovery-Fehler] {e}")
            time.sleep(0.1)  # CPU-Last reduzieren

    def process_outgoing():
        """
        @brief Thread zur Verarbeitung von WHOIS-Anfragen aus der UI.
        @details
        Bereinigt WHOIS-Eingabe (z. B. 'WHOIS B') → sendet korrektes SLCP.
        """
        nonlocal joined
        if receive_only:
           return  # WHOIS-Sender deaktiviert
        while True:
            try:
                item = queue_from_ui.get(timeout=0.1)
                raw = item["data"].strip()
                parsed = parse_message(raw)
                command = parsed["command"]
                if command == "JOIN":
                   joined = True
                   print("[Discovery] JOIN erkannt – du bist aktiv.")

                elif command == "LEAVE":
                    joined = False
                    print("[Discovery] LEAVE erkannt – du bist jetzt offline.")

                elif command == "WHOIS":
                    if not joined:
                       print("[Discovery] WHOIS-Anfrage blockiert – du bist nicht joined.")
                       continue

                    handle = parsed["params"][0]
                    whois_msg = build_message("WHOIS", handle, str(local_port))
                    broadcast_ip = detect_broadcast_address()
                    udp_socket.sendto(whois_msg.encode("utf-8"), (broadcast_ip, whois_port))

                    print(f"[Discovery] WHOIS gesendet (Broadcast): {whois_msg}")
            except Empty:
                 pass  # keine Nachricht = kein Problem
            except Exception as e:
                 print("[Discovery-WHOIS-Fehler]")
                 traceback.print_exc()


    # === Threads für eingehend und ausgehend starten ===
    threading.Thread(target=receive_whois, daemon=True).start()
    threading.Thread(target=process_outgoing, daemon=True).start()

    # Hauptprozess bleibt aktiv (z. B. für Logging), blockiert aber nichts
    while True:
        time.sleep(1)

def get_own_ip() -> str:
    """
    @brief Ermittelt die lokale IP-Adresse des aktuellen Rechners.
    @details
    Es wird eine "Dummy-Verbindung" zu 8.8.8.8 (Google DNS) aufgebaut,
    nur um die IP des ausgehenden Interfaces herauszufinden.

    @return Lokale IP-Adresse als String, z. B. "192.168.0.23"
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Keine echte Datenübertragung nötig
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"  # Fallback bei Fehlern oder keiner Verbindung
