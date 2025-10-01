# discovery.py

import socket
import threading
import time
import crypto_utils 

# --- CONFIGURATION ---
DISCOVERY_PORT = 50000
DISCOVERY_MESSAGE = "LOCAL_CHAT_DISCOVER_V2_SECURE"
BROADCAST_INTERVAL = 5

def get_lan_ip():
    """Finds the local IP address of the machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class Discovery:
    def __init__(self, username, public_key):
        self.username = username
        self.public_key_str = crypto_utils.public_key_to_string(public_key)
        self.lan_ip = get_lan_ip()
        self.online_users = {}
        self.running = True
        self.lock = threading.Lock()
        self.listener_thread = threading.Thread(target=self._listen_for_peers, daemon=True)
        self.broadcaster_thread = threading.Thread(target=self._broadcast_presence, daemon=True)

    def start(self):
        print(f"[Discovery] Starting service for user '{self.username}' on IP {self.lan_ip}...")
        self.listener_thread.start()
        self.broadcaster_thread.start()
        print("[Discovery] Service running in the background.")

    def stop(self):
        self.running = False

    def get_online_users(self):
        with self.lock:
            current_time = time.time()
            # Filter out users who haven't been heard from in a while
            active_users = {}
            for user, (ip, pub_key, last_seen) in self.online_users.items():
                if current_time - last_seen < (BROADCAST_INTERVAL * 3):
                    active_users[user] = (ip, pub_key, last_seen)
            self.online_users = active_users
            return self.online_users

    def _listen_for_peers(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', DISCOVERY_PORT))
            s.settimeout(1.0)
            while self.running:
                try:
                    data, addr = s.recvfrom(4096)
                    message = data.decode()
                    if message.startswith(DISCOVERY_MESSAGE):
                        parts = message.split("::", 3)
                        peer_username, peer_ip, peer_public_key_str = parts[1], parts[2], parts[3]
                        
                        if peer_username != self.username:
                            with self.lock:
                                peer_public_key = crypto_utils.string_to_public_key(peer_public_key_str)
                                if peer_username not in self.online_users:
                                    print(f"[Discovery] Discovered new user: {peer_username} at {peer_ip}")
                                self.online_users[peer_username] = (peer_ip, peer_public_key, time.time())
                except socket.timeout:
                    continue
                except Exception:
                    pass # Ignore parsing errors from malformed packets

    def _broadcast_presence(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            message = f"{DISCOVERY_MESSAGE}::{self.username}::{self.lan_ip}::{self.public_key_str}".encode()
            while self.running:
                try:
                    s.sendto(message, ('<broadcast>', DISCOVERY_PORT))
                    time.sleep(BROADCAST_INTERVAL)
                except Exception:
                    break