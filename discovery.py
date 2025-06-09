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
