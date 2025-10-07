# network_core.py

import socket
import threading
import os
import base64
import crypto_utils

TCP_PORT = 50001         # Port number for TCP communication
CHUNK_SIZE = 4096        # Size of each data chunk for file transfer

class NetworkCore:
    """
    Core networking class for LAN chat application.
    Handles sending/receiving messages and files over TCP.
    Uses RSA for message encryption and AES for file encryption.
    """

    def __init__(self, username, discovery_service, private_key, message_callback, file_callback):
        """
        Initialize the NetworkCore instance.

        Args:
            username (str): Local user's username.
            discovery_service: Service to discover online users.
            private_key: RSA private key for decryption.
            message_callback: Function to call when a message is received.
            file_callback: Function to call for file transfer events.
        """
        self.username = username
        self.discovery_service = discovery_service
        self.private_key = private_key
        self.message_callback = message_callback
        self.file_callback = file_callback
        self.running = True
        # Start the TCP server in a separate thread to handle incoming connections
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)

    def start(self):
        """
        Start the TCP server thread.
        This allows the application to listen for incoming messages and file transfers.
        """
        self.server_thread.start()

    def stop(self):
        """
        Stop the TCP server.
        Sets the running flag to False and unblocks the server's accept call
        by connecting to itself, allowing the thread to exit gracefully.
        """
        self.running = False
        try:
            # Connect to the server to unblock accept()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', TCP_PORT))
        except:
            pass

    def _run_server(self):
        """
        Main server loop.
        Listens for incoming TCP connections and spawns handler threads for each client.
        Handles both message and file transfer requests.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', TCP_PORT))
            server_socket.listen(5)
            print(f"[NetworkCore] TCP Server listening on port {TCP_PORT}...")
            while self.running:
                try:
                    # Accept incoming connection
                    client_socket, addr = server_socket.accept()
                    # Handle each client in a separate thread for concurrency
                    handler = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
                    handler.start()
                except:
                    break

    def _handle_client(self, client_socket):
        """
        Handles incoming data from a client.
        Supports both message and file transfers.
        Decodes the header to determine the type of data and processes accordingly.
        """
        with client_socket:
            try:
                # Receive the header data (message or file transfer info)
                header_data = client_socket.recv(CHUNK_SIZE)
                if not header_data: return

                header = header_data.decode()
                parts = header.split("::")
                data_type = parts[0]
                sender_username = parts[-1]

                if data_type == "MSG":
                    # Handle incoming encrypted message
                    encoded_message = parts[1]
                    encrypted_message = base64.b64decode(encoded_message)
                    # Decrypt message using local private key
                    decrypted_message = crypto_utils.decrypt_with_rsa(self.private_key, encrypted_message)
                    # Pass the decrypted message to the callback for display
                    self.message_callback(sender_username, decrypted_message.decode('utf-8'))

                elif data_type == "FILE":
                    # Handle incoming file transfer
                    filename, filesize_str, encoded_aes_key = parts[1], parts[2], parts[3]
                    filesize = int(filesize_str)

                    # Decode and decrypt the AES key using local private RSA key
                    encrypted_aes_key = base64.b64decode(encoded_aes_key)
                    aes_key = crypto_utils.decrypt_with_rsa(self.private_key, encrypted_aes_key)

                    # --- HANDSHAKE PART 1: Receiver sends "READY" signal ---
                    client_socket.sendall(b"READY")
                    # --------------------------------------------------------

                    # Prepare directory for received files
                    os.makedirs(f"received_files/{sender_username}", exist_ok=True)
                    filepath = os.path.join(f"received_files/{sender_username}", filename)

                    # Notify start of file transfer via callback
                    self.file_callback("start", sender_username, filename)

                    # Receive and decrypt file chunks until the entire file is received
                    with open(filepath, "wb") as f:
                        bytes_received = 0
                        while bytes_received < filesize:
                            # AES-GCM adds 12 bytes for IV and 16 for the auth tag
                            encrypted_chunk = client_socket.recv(CHUNK_SIZE + 28)
                            if not encrypted_chunk: break
                            decrypted_chunk = crypto_utils.decrypt_file_chunk(aes_key, encrypted_chunk)
                            f.write(decrypted_chunk)
                            bytes_received += len(decrypted_chunk)

                    # Notify end of file transfer via callback
                    self.file_callback("end", sender_username, filename)

            except Exception as e:
                print(f"[Handler] Error: {e}")

    def send_message(self, target_username, message):
        """
        Send an encrypted message to a target user.

        Args:
            target_username (str): Recipient's username.
            message (str): Message to send.

        Returns:
            bool: True if sent, False if user not found.
        """
        # Get the list of online users from the discovery service
        users = self.discovery_service.get_online_users()
        if target_username in users:
            # Extract recipient's IP and public key
            target_ip, target_public_key, _ = users[target_username]
            # Encrypt the message using recipient's public RSA key
            encrypted_message = crypto_utils.encrypt_with_rsa(target_public_key, message.encode('utf-8'))
            # Encode the encrypted message in base64 for safe transport
            encoded_message = base64.b64encode(encrypted_message).decode('utf-8')
            # Prepare the message header
            header = f"MSG::{encoded_message}::{self.username}".encode()
            # Send the message in a separate thread to avoid blocking
            threading.Thread(target=self._send_tcp_data, args=(target_ip, header), daemon=True).start()
        else:
            print(f"User '{target_username}' not found.")
            return False
        return True

    def send_file(self, target_username, filepath):
        """
        Send a file to a target user using AES encryption.

        Args:
            target_username (str): Recipient's username.
            filepath (str): Path to the file to send.

        Returns:
            bool: True if sent, False if user or file not found.
        """
        # Check if the file exists before proceeding
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return False

        # Get the list of online users from the discovery service
        users = self.discovery_service.get_online_users()
        if target_username in users:
            # Extract recipient's IP and public key
            target_ip, target_public_key, _ = users[target_username]

            # Generate a random AES key for encrypting the file contents
            aes_key = crypto_utils.generate_aes_key()
            # Encrypt the AES key using the recipient's public RSA key for secure transmission
            encrypted_aes_key = crypto_utils.encrypt_with_rsa(target_public_key, aes_key)
            # Encode the encrypted AES key in base64 for safe transport
            encoded_aes_key = base64.b64encode(encrypted_aes_key).decode('utf-8')

            # Get the filename and its size for the header
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)

            # Prepare the header containing file metadata and sender info
            header = f"FILE::{filename}::{filesize}::{encoded_aes_key}::{self.username}".encode()

            # Start a new thread to handle the file transfer so the main thread isn't blocked
            threading.Thread(
                target=self._send_file_data_robust,
                args=(target_ip, header, filepath, aes_key),
                daemon=True
            ).start()
        else:
            # If the target user is not online, print an error and return False
            print(f"User '{target_username}' not found.")
            return False
        # Return True to indicate the file transfer was initiated
        return True

    def _send_tcp_data(self, target_ip, data):
        """
        Send raw TCP data to a target IP.

        Args:
            target_ip (str): Recipient's IP address.
            data (bytes): Data to send.
        """
        try:
            # Create a TCP socket and connect to the recipient
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                # Send the data (message header)
                s.sendall(data)
        except Exception as e:
            print(f"[TCP Send] Error: {e}")

    def _send_file_data_robust(self, target_ip, header, filepath, aes_key):
        """
        Send file data to a target IP with handshake confirmation.

        Args:
            target_ip (str): Recipient's IP address.
            header (bytes): File transfer header.
            filepath (str): Path to the file to send.
            aes_key (bytes): AES key for encryption.
        """
        try:
            # Create a TCP socket and connect to the recipient
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                # Send the file transfer header
                s.sendall(header)

                # --- HANDSHAKE PART 2: Sender waits for "READY" signal ---
                confirmation = s.recv(1024)
                if confirmation != b"READY":
                    raise Exception("Receiver did not send READY confirmation.")
                # ----------------------------------------------------------

                # Open the file and send it in encrypted chunks
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk: break
                        # Encrypt each chunk using AES-GCM
                        encrypted_chunk = crypto_utils.encrypt_file_chunk(aes_key, chunk)
                        s.sendall(encrypted_chunk)
        except Exception as e:
            print(f"[File Send] Error: {e}")