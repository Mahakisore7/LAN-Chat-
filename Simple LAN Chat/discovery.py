import socket
import threading
import time

# --- CONFIGURATION ---
# The port that our application will use for discovery.
# Ports 1-1024 are "well-known" (e.g., HTTP is 80). We use a high-numbered port.
DISCOVERY_PORT = 50000

# A special message header to identify our app's packets.
DISCOVERY_MESSAGE = "LOCAL_CHAT_DISCOVER_V1"

# How often (in seconds) we broadcast our presence.
BROADCAST_INTERVAL = 5

class Discovery:
    """
    This class handles the automatic discovery of other users on the network.
    It runs two threads: one for broadcasting our presence and one for listening
    for others.
    """
    def __init__(self, username):
        self.username = username
        self.online_users = {}  # A dictionary to store {username: (ip_address, last_seen_time)}
        self.running = True
        self.lock = threading.Lock() # To safely modify the online_users list from multiple threads

        # Start the listener and broadcaster threads
        self.listener_thread = threading.Thread(target=self._listen_for_peers, daemon=True)
        self.broadcaster_thread = threading.Thread(target=self._broadcast_presence, daemon=True)

    def start(self):
        """Starts the discovery service."""
        print(f"[Discovery] Starting service for user '{self.username}'...")
        self.listener_thread.start()
        self.broadcaster_thread.start()
        print("[Discovery] Service running in the background.")

    def stop(self):
        """Stops the discovery service."""
        print("[Discovery] Stopping service...")
        self.running = False
        # The threads are daemon threads, so they will exit when the main program exits.

    def get_online_users(self):
        """
        Returns a dictionary of currently online users.
        Also removes users who haven't been seen in a while (e.g., > 15 seconds).
        """
        with self.lock:
            current_time = time.time()
            # Create a new dictionary to avoid modifying the one we're iterating over
            active_users = {}
            for user, (ip, last_seen) in self.online_users.items():
                if current_time - last_seen < (BROADCAST_INTERVAL * 3): # If last seen within 3 broadcast intervals
                    active_users[user] = (ip, last_seen)
                else:
                    print(f"[Discovery] User '{user}' timed out.")
            self.online_users = active_users
            return self.online_users

    def _listen_for_peers(self):
        """
        This function runs in its own thread and listens for UDP broadcast packets.
        """
        # Create a UDP socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Bind the socket to listen on the discovery port from any IP address
            s.bind(('', DISCOVERY_PORT))
            s.settimeout(1.0) # Set a timeout so the loop can check self.running

            print(f"[Listener] Listening for peers on UDP port {DISCOVERY_PORT}...")
            while self.running:
                try:
                    # Wait to receive data
                    data, addr = s.recvfrom(1024) # buffer size is 1024 bytes
                    message = data.decode()
                    
                    # Check if it's our app's discovery message
                    if message.startswith(DISCOVERY_MESSAGE):
                        parts = message.split("::")
                        peer_username = parts[1]
                        
                        # We don't want to add ourselves to the list
                        if peer_username != self.username:
                            with self.lock:
                                # Update the user's entry with their IP and the current time
                                if peer_username not in self.online_users:
                                    print(f"[Discovery] Discovered new user: {peer_username} at {addr[0]}")
                                self.online_users[peer_username] = (addr[0], time.time())

                except socket.timeout:
                    # This is expected. It allows the while loop to check the 'running' flag.
                    continue
                except Exception as e:
                    print(f"[Listener] An error occurred: {e}")

    def _broadcast_presence(self):
        """
        This function runs in its own thread and broadcasts our presence every few seconds.
        """
        # Create a UDP socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Set a special socket option to allow broadcasting
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            # The message we will send
            message = f"{DISCOVERY_MESSAGE}::{self.username}".encode()
            
            print("[Broadcaster] Starting to broadcast presence...")
            while self.running:
                try:
                    # Send the message to the broadcast address on the discovery port.
                    # '<broadcast>' is a special address that sends to 255.255.255.255
                    s.sendto(message, ('<broadcast>', DISCOVERY_PORT))
                    time.sleep(BROADCAST_INTERVAL)
                except Exception as e:
                    print(f"[Broadcaster] An error occurred: {e}")
                    break

# --- MAIN EXECUTION ---
# This part of the script is for testing the Discovery class directly.
if __name__ == "__main__":
    # Get a username from the command line or use a default
    my_username = input("Enter your username: ") or "DefaultUser"
    
    discovery_service = Discovery(my_username)
    discovery_service.start()
    
    try:
        while True:
            # Print the list of online users every 10 seconds
            print("\n--- Online Users ---")
            users = discovery_service.get_online_users()
            if users:
                for user, (ip, last_seen) in users.items():
                    print(f"- {user} ({ip})")
            else:
                print("Scanning for other users...")
            print("--------------------")
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nShutting down...")
        discovery_service.stop()
