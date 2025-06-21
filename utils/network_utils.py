import socket, struct, fcntl
import os
import array
def get_broadcast_for_iface(iface: str) -> str:
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
    import netifaces
    candidates = []

    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for entry in addrs[netifaces.AF_INET]:
                if 'broadcast' in entry:
                    broadcast = entry['broadcast']
                    ip = entry.get('addr', '?')
                    print(f"[INTERFACE] {iface}: IP={ip}, Broadcast={broadcast}")
                    candidates.append(broadcast)

    if candidates:
        return candidates[0]
    return "255.255.255.255"

