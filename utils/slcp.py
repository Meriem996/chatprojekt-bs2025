"""
@file slcp.py
@brief Generierung und Parsing von SLCP-Protokollnachrichten (JOIN, LEAVE, MSG, IMG, WHOIS, IAM)

@details
Dieses Modul stellt zwei zentrale Funktionen bereit:
- build_message(): erstellt eine gültige SLCP-Nachricht aus Befehl + Parametern
- parse_message(): analysiert eine eingehende SLCP-Zeile und extrahiert Befehl + Parameter

Die Nachrichten sind UTF-8 codiert, mit Zeilenumbruch, optionalen Escape-Sequenzen
und dürfen 512 Byte nicht überschreiten (siehe SLCP-Protokolldefinition).
"""

import re

MAX_MESSAGE_LENGTH = 512     # Maximale Länge laut SLCP-Spezifikation (in Bytes, UTF-8)
LINE_ENDING = "\n"           # Nachrichten enden immer mit Zeilenumbruch
VALID_COMMANDS = {"JOIN", "LEAVE", "MSG", "IMG", "WHOIS", "IAM"}  # erlaubte SLCP-Kommandos


def escape_param(param: str) -> str:
    """
    @brief Wandelt einen Parameter so um, dass Leerzeichen und Sonderzeichen korrekt dargestellt werden.
    @param param Ein einzelner Parameterwert (z. B. Benutzername oder Nachricht)
    @return Escaped Parameter als String – in Anführungszeichen, wenn nötig
    """

    # Wenn Leerzeichen oder Sonderzeichen enthalten sind, escapen
    if ' ' in param or '"' in param or '\\' in param:
        escaped = param.replace('\\', '\\\\').replace('"', '\\"')  # Backslashes und Anführungszeichen escapen
        return f'"{escaped}"'  # in doppelte Anführungszeichen setzen

    return param  # Unverändert zurückgeben, wenn unkritisch


def build_message(command: str, *params: str) -> str:
    """
    @brief Baut eine SLCP-konforme Nachricht als String.
    @param command SLCP-Kommando (z. B. MSG, JOIN, IMG, WHOIS ...)
    @param params Beliebig viele Parameter als Strings
    @return Vollständige Nachricht mit Zeilenumbruch (ready to send)
    @raises ValueError Wenn das Kommando ungültig ist oder Nachricht zu lang
    """

    if command not in VALID_COMMANDS:
        raise ValueError(f"Ungültiger SLCP-Befehl: {command}")

    # Parameter einzeln escapen (z. B. "Max Mustermann" → "Max Mustermann")
    escaped_params = [escape_param(str(p)) for p in params]

    # Zusammensetzen
    message = f"{command} {' '.join(escaped_params)}{LINE_ENDING}"

    # Längenprüfung (UTF-8)
    if len(message.encode("utf-8")) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Nachricht überschreitet {MAX_MESSAGE_LENGTH} Byte (UTF-8)")

    return message


def parse_message(raw_data: str) -> dict:
    """
    @brief Parst eine eingehende SLCP-Nachricht und zerlegt sie in Kommando + Parameter.
    @param raw_data Komplette SLCP-Zeile (z. B. MSG Max "Hallo Welt\n")
    @return Dictionary mit:
        - "command": SLCP-Befehl als String
        - "params": Liste aller Parameter (bereinigt, decoded)
    @raises ValueError Bei leerer Eingabe, Syntaxfehler oder unbekanntem Befehl
    """

    # Zeilenumbruch entfernen + leere Nachricht verhindern
    raw_data = raw_data.strip()
    if not raw_data:
        raise ValueError("Leere Nachricht")

    # Regex: entweder ein quoted string ("mit leerzeichen") oder ein normales Wort
    pattern = r'"((?:[^"\\]|\\.)*)"|(\S+)'  # erlaubt escape innerhalb von Anführungszeichen

    # Alle passenden Token finden
    matches = re.findall(pattern, raw_data)

    parts = []
    for quoted, plain in matches:
        if quoted:
            # decode unicode escapes (z. B. \" → ")
            parts.append(bytes(quoted, "utf-8").decode("unicode_escape"))
        else:
            parts.append(plain)

    if not parts:
        raise ValueError("Unlesbare Nachricht")

    command = parts[0]
    params = parts[1:]

    if command not in VALID_COMMANDS:
        raise ValueError(f"Unbekannter Befehl: {command}")

    return {
        "command": command,
        "params": params
    }