"""
@file discovery.py
@brief Automatische Peer-Erkennung (Discovery) über WHOIS/IAM im lokalen Netzwerk.

@details
Dieses Modul gehört zum BSRN-Chatprogramm und ist verantwortlich für:
- Empfang und Verarbeitung von WHOIS-Anfragen
- Antwort mit IAM-Nachrichten, wenn Handle übereinstimmt
- Senden von Auto-Replies bei Inaktivität (nicht „joined“)
- Weiterleitung von IAM-Daten an die UI

Zwei Threads laufen parallel:
- receive_whois(): verarbeitet eingehende WHOIS/IAM
- process_outgoing(): verarbeitet eigene WHOIS-Anfragen
"""

import socket, threading, time, traceback
from queue import Empty
from utils.slcp import parse_message, build_message
from utils.config import get_config_value
from utils.network_utils import detect_broadcast_address

def run_discovery(queue_from_ui, queue_to_ui_net, config, receive_only=False):
    """
    @brief Startet den Discovery-Prozess für WHOIS/IAM-Kommunikation.

    @param queue_from_ui Eingehende WHOIS-Befehle (von CLI)
    @param queue_to_ui_net IAM-Antworten für die Benutzeroberfläche
    @param config Konfigurationsdaten mit Handle, Port, usw.
    @param receive_only Optional: Nur Zuhören, kein aktives Senden
    """
    
    # Konfiguration auslesen
    whois_port = config["whoisport"]
    local_handle = config["handle"]
    autoreply = get_config_value("autoreply")
    local_port = config["port"]
    joined = False  # Wurde vorher JOIN gesendet?

    # UDP-Socket vorbereiten für Broadcast/Empfang
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except AttributeError:
        pass
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", whois_port))

    print(f"[Discovery] Listening on UDP {whois_port}")

    def receive_whois():
        """
        @brief Thread: Reagiert auf eingehende WHOIS/IAM-Nachrichten.

        @details
        - Erkennt WHOIS, prüft auf eigenen Handle, sendet ggf. IAM oder Auto-Reply
        - Erkennt IAM und gibt Info an UI weiter
        """
        nonlocal joined
        while True:
            try:
                # Nachricht empfangen
                data, addr = udp_socket.recvfrom(1024)
                msg = data.decode().strip()
                parsed = parse_message(msg)

                # WHOIS → prüfen ob an mich
                if parsed["command"] == "WHOIS" and parsed["params"][0] == local_handle:
                    if not joined:
                        print("[Discovery] WHOIS empfangen, aber nicht joined.")
                        # Bei Inaktivität optional Auto-Reply senden
                        try:
                            port = int(parsed["params"][1])
                            if autoreply:
                                rmsg = build_message("MSG", local_handle, "[autoreply] " + autoreply)
                                udp_socket.sendto(rmsg.encode(), (addr[0], port))
                                print(f"[Discovery] Auto-Reply an {addr[0]}:{port}")
                        except:
                            pass
                        continue  # Keine IAM senden

                    # IAM senden
                    try:
                        port = int(parsed["params"][1])
                        iam_msg = build_message("IAM", local_handle, get_own_ip(), local_port)
                        bcast = detect_broadcast_address()
                        udp_socket.sendto(iam_msg.encode(), (bcast, whois_port))
                        print(f"[Discovery] IAM an {bcast}:{whois_port}")
                    except:
                        continue

                # IAM empfangen → an UI senden
                elif parsed["command"] == "IAM":
                    h, ip, port = parsed["params"]
                    queue_to_ui_net.put({
                        "type": "iam",
                        "handle": h,
                        "ip": ip,
                        "port": int(port)
                    })

            except Exception as e:
                print(f"[Discovery-Fehler] {e}")
            time.sleep(0.1)

    def process_outgoing():
        """
        @brief Thread: Sendet WHOIS-Anfragen ins Netzwerk (aus CLI).

        @details
        Erkennt JOIN, LEAVE, WHOIS → verarbeitet Zustand und verschickt WHOIS.
        """
        nonlocal joined
        if receive_only:
            return
        while True:
            try:
                # CLI-Eingabe abholen
                item = queue_from_ui.get(timeout=0.1)
                raw = item["data"].strip()
                parsed = parse_message(raw)
                cmd = parsed["command"]

                # JOIN/LEAVE aktualisiert Zustand
                if cmd == "JOIN":
                    joined = True
                    print("[Discovery] JOIN → aktiv")
                elif cmd == "LEAVE":
                    joined = False
                    print("[Discovery] LEAVE → inaktiv")
                elif cmd == "WHOIS":
                    if not joined:
                        print("[Discovery] WHOIS blockiert – nicht joined.")
                        continue
                    # WHOIS senden
                    handle = parsed["params"][0]
                    msg = build_message("WHOIS", handle, str(local_port))
                    bcast = detect_broadcast_address()
                    udp_socket.sendto(msg.encode(), (bcast, whois_port))
                    print(f"[Discovery] WHOIS gesendet: {msg}")

            except Empty:
                pass  # keine Nachricht da
            except Exception:
                print("[Discovery-WHOIS-Fehler]")
                traceback.print_exc()

    # Threads starten
    threading.Thread(target=receive_whois, daemon=True).start()
    threading.Thread(target=process_outgoing, daemon=True).start()

    # Hauptprozess bleibt aktiv
    while True:
        time.sleep(1)

def get_own_ip() -> str:
    """
    @brief Ermittelt lokale IP-Adresse des Systems.

    @details
    Baut Dummy-Verbindung zu 8.8.8.8 auf, um lokale IP herauszufinden.
    Es findet kein echter Datentransfer statt.

    @return Lokale IP-Adresse (z. B. „192.168.0.15“), Fallback: „127.0.0.1“
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"
