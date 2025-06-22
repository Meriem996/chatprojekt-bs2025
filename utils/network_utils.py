"""
@file network_utils.py
@brief Netzwerkwerkzeuge zur Bestimmung von Broadcast-Adressen.

@details
Diese Datei enthält Hilfsfunktionen zur Ermittlung von Netzwerk-Broadcast-Adressen.
Sie werden benötigt, um WHOIS- oder IAM-Nachrichten korrekt im lokalen Netzwerk zu versenden.

Zwei Varianten werden unterstützt:
- low-level ioctl-Aufruf (funktioniert nur unter Linux)
- netifaces-basierte Erkennung für alle Plattformen (robuster)
"""

import socket, struct, fcntl
import os, array

def get_broadcast_for_iface(iface: str) -> str:
    """
    @brief Ermittelt die Broadcast-Adresse einer bestimmten Netzwerkschnittstelle.

    @details
    Nutzt low-level `ioctl`-Aufruf auf Linux-Systemen mit dem IOCTL-Code `SIOCGIFBRDADDR` (0x8919),
    um die Broadcast-Adresse für eine gegebene Netzwerkschnittstelle (`eth0`, `wlan0`, usw.) zu erhalten.

    @param iface Name der Netzwerkschnittstelle (z. B. "eth0" oder "wlan0")
    @return Broadcast-Adresse als String (z. B. "192.168.0.255"), oder `None` bei Fehler

    @note Funktioniert nur unter Linux. Unter Windows wird automatisch `None` zurückgegeben.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = fcntl.ioctl(
            s.fileno(),
            0x8919,  # SIOCGIFBRDADDR
            struct.pack('256s', bytes(iface[:15], 'utf-8'))
        )
        return socket.inet_ntoa(ifreq[20:24])
    except Exception:
        return None

def detect_broadcast_address():
    """
    @brief Sucht nach verfügbaren Broadcast-Adressen im lokalen System.

    @details
    Nutzt das Modul `netifaces`, um alle verfügbaren Netzwerkinterfaces zu durchlaufen.
    Für jede Schnittstelle wird geprüft, ob eine IPv4-Adresse mit zugehöriger Broadcast-Adresse existiert.
    Die erste gefundene Adresse wird zurückgegeben. Falls keine gefunden wird,
    wird "255.255.255.255" als Fallback verwendet.

    @return Eine gültige Broadcast-Adresse (z. B. "192.168.0.255") oder der Default "255.255.255.255"

    @note Diese Funktion ist plattformunabhängig und robuster als `get_broadcast_for_iface`.
    """
    import netifaces
    candidates = []

    # Alle Interfaces durchgehen
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for entry in addrs[netifaces.AF_INET]:
                if 'broadcast' in entry:
                    broadcast = entry['broadcast']
                    ip = entry.get('addr', '?')
                    print(f"[INTERFACE] {iface}: IP={ip}, Broadcast={broadcast}")
                    candidates.append(broadcast)

    # Ersten gültigen Kandidaten zurückgeben
    if candidates:
        return candidates[0]

    # Fallback
    return "255.255.255.255"
