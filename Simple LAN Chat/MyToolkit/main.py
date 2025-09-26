import socket
import threading
import time
import os
from discovery import Discovery # We are importing the class we built in discovery.py

# --- CONFIGURATION ---
TCP_PORT = 50001 # A separate port for reliable TCP communication

class Communication:
    """
    Manages all direct, reliable (TCP) communication for chat and file transfers.
    """
    def __init__(self, username, discovery_service):
        self.username = username
        self.discovery_service = discovery_service
        self.running = True
        # The main server thread listens for new connections
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)

    def start(self):
        """Starts the main TCP server thread."""
        self.server_thread.start()

    def stop(self):
        """Stops the communication service."""
        self.running = False
        # A trick to unblock the server socket accept() call
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', TCP_PORT))
        except ConnectionRefusedError:
            pass # Expected if the server is already shutting down

    def _run_server(self):
        """
        This is the "TCP Server" worker. It listens for incoming connection requests.
        """
        # Create a TCP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            # Allow the address to be reused to avoid "Address already in use" errors on restart
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind the socket to listen on our designated TCP port
            server_socket.bind(('', TCP_PORT))
            # Start listening, allowing up to 5 queued connections
            server_socket.listen(5)
            print(f"[Communication] TCP Server listening on port {TCP_PORT}...")

            while self.running:
                try:
                    # This is a blocking call. The thread pauses here waiting for a client to connect.
                    client_socket, addr = server_socket.accept()
                    # When a client connects, spawn a new thread to handle them.
                    # This allows the server to handle multiple clients at once.
                    handler = threading.Thread(target=self._handle_client, args=(client_socket, addr), daemon=True)
                    handler.start()
                except Exception as e:
                    if self.running:
                        print(f"[Server] An error occurred: {e}")
                    break
        print("[Server] TCP Server has shut down.")


    def _handle_client(self, client_socket, addr):
        """
        This is the "Handler" worker. One of these is created for each client that connects.
        """
        print(f"[Server] Accepted connection from {addr}")
        with client_socket:
            try:
                # First, receive the header to know what kind of data is coming.
                header_data = client_socket.recv(1024)
                if not header_data:
                    return
                
                header = header_data.decode()
                parts = header.split("::")
                data_type = parts[0]

                if data_type == "MSG":
                    message = parts[1]
                    sender_username = parts[2]
                    print(f"\n[{sender_username} says]: {message}\n> ", end="")
                
                elif data_type == "FILE":
                    filename = parts[1]
                    filesize = int(parts[2])
                    sender_username = parts[3]
                    
                    print(f"\nReceiving file '{filename}' ({filesize} bytes) from {sender_username}...")
                    
                    # Read the file data in chunks
                    with open(filename, 'wb') as f:
                        bytes_received = 0
                        while bytes_received < filesize:
                            chunk = client_socket.recv(4096)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_received += len(chunk)
                    print(f"File '{filename}' received successfully.\n> ", end="")

            except Exception as e:
                print(f"[Handler] Error with client {addr}: {e}")

    def _send_data(self, target_ip, data):
        """Helper function to establish a TCP connection and send data."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                s.sendall(data)
            return True
        except ConnectionRefusedError:
            print(f"[Communication] Connection to {target_ip} was refused. Is the app running there?")
        except Exception as e:
            print(f"[Communication] Error sending data to {target_ip}: {e}")
        return False

    def send_message(self, target_username, message):
        """Sends a text message to a specific user."""
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip = users[target_username][0]
            header = f"MSG::{message}::{self.username}".encode()
            print(f"Sending message to {target_username}...")
            self._send_data(target_ip, header)
        else:
            print(f"User '{target_username}' not found.")

    def send_file(self, target_username, filepath):
        """Sends a file to a specific user."""
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return

        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip = users[target_username][0]
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            header = f"FILE::{filename}::{filesize}::{self.username}".encode()
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    print(f"Connecting to {target_username} to send file...")
                    s.connect((target_ip, TCP_PORT))
                    # 1. Send the header first
                    s.sendall(header)
                    time.sleep(0.1) # Small delay to ensure header is processed first
                    # 2. Send the file content
                    print(f"Sending file '{filename}'...")
                    with open(filepath, 'rb') as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break
                            s.sendall(chunk)
                    print(f"File '{filename}' sent successfully.")
            except Exception as e:
                print(f"[File Send] Error: {e}")
        else:
            print(f"User '{target_username}' not found.")

def print_help():
    print("\n--- Commands ---")
    print("msg <username> <message>  - Send a message to a user.")
    print("send <username> <filepath> - Send a file to a user.")
    print("online                    - Show the list of online users.")
    print("help                      - Show this help message.")
    print("exit                      - Quit the application.")
    print("----------------")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    my_username = input("Enter your username: ") or f"User_{int(time.time()) % 1000}"
    
    # 1. Start the Discovery Service
    discovery_service = Discovery(my_username)
    discovery_service.start()
    
    # 2. Start the Communication Service
    communication_service = Communication(my_username, discovery_service)
    communication_service.start()
    
    print_help()

    try:
        while True:
            # 3. Main command loop
            command_input = input("> ")
            parts = command_input.split(" ", 2)
            command = parts[0].lower()

            if command == "msg":
                if len(parts) < 3:
                    print("Usage: msg <username> <message>")
                else:
                    communication_service.send_message(parts[1], parts[2])
            
            elif command == "send":
                if len(parts) < 3:
                    print("Usage: send <username> <filepath>")
                else:
                    communication_service.send_file(parts[1], parts[2])

            elif command == "online":
                print("\n--- Online Users ---")
                users = discovery_service.get_online_users()
                if users:
                    for user, (ip, last_seen) in users.items():
                        print(f"- {user} ({ip})")
                else:
                    print("Scanning for other users...")
                print("--------------------")
            
            elif command == "help":
                print_help()

            elif command == "exit":
                break
                
            else:
                if command:
                    print("Unknown command. Type 'help' for a list of commands.")

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # 4. Cleanly stop all services
        discovery_service.stop()
        communication_service.stop()
        print("Application has been shut down.")

