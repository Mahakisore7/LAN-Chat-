import socket
import threading
import os
import base64
import crypto_utils

TCP_PORT = 50001
CHUNK_SIZE = 4096

class NetworkCore:
    def __init__(self, username, discovery_service, private_key, message_callback, file_callback):
        self.username = username
        self.discovery_service = discovery_service
        self.private_key = private_key
        self.message_callback = message_callback
        self.file_callback = file_callback
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)

    def start(self):
        self.server_thread.start()

    def stop(self):
        self.running = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', TCP_PORT))
        except:
            pass

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', TCP_PORT))
            server_socket.listen(5)
            print(f"[NetworkCore] TCP Server listening on port {TCP_PORT}...")
            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    handler = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
                    handler.start()
                except:
                    break

    def _handle_client(self, client_socket):
        with client_socket:
            try:
                header_data = client_socket.recv(CHUNK_SIZE)
                if not header_data: return
                
                header = header_data.decode()
                parts = header.split("::")
                data_type = parts[0]
                sender_username = parts[-1]

                if data_type == "MSG":
                    # This part remains the same
                    encoded_message = parts[1]
                    encrypted_message = base64.b64decode(encoded_message)
                    decrypted_message = crypto_utils.decrypt_with_rsa(self.private_key, encrypted_message)
                    self.message_callback(sender_username, decrypted_message)
                
                elif data_type == "FILE":
                    filename, filesize_str, encoded_aes_key = parts[1], parts[2], parts[3]
                    filesize = int(filesize_str)
                    
                    # 1. Receiver does its time-consuming work
                    encrypted_aes_key = base64.b64decode(encoded_aes_key)
                    aes_key = crypto_utils.decrypt_with_rsa(self.private_key, encrypted_aes_key)
                    
                    # --- NEW STEP: THE "READY" ACKNOWLEDGEMENT ---
                    # 2. Receiver tells the sender, "I'm ready for the file now!"
                    client_socket.sendall(b"READY")
                    # ----------------------------------------------
                    
                    os.makedirs(f"received_files/{sender_username}", exist_ok=True)
                    filepath = os.path.join(f"received_files/{sender_username}", filename)
                    
                    self.file_callback("start", sender_username, filename)
                    
                    # 3. Receiver starts listening for the file data
                    with open(filepath, "wb") as f:
                        bytes_received = 0
                        while bytes_received < filesize:
                            encrypted_chunk = client_socket.recv(CHUNK_SIZE + 28)
                            if not encrypted_chunk: break
                            decrypted_chunk = crypto_utils.decrypt_file_chunk(aes_key, encrypted_chunk)
                            f.write(decrypted_chunk)
                            bytes_received += len(decrypted_chunk)
                    
                    self.file_callback("end", sender_username, filename)

            except Exception as e:
                print(f"[Handler] Error: {e}")

    # send_message function remains the same as before
    def send_message(self, target_username, message):
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip, target_public_key, _ = users[target_username]
            encrypted_message = crypto_utils.encrypt_with_rsa(target_public_key, message.encode('utf-8'))
            encoded_message = base64.b64encode(encrypted_message).decode('utf-8')
            header = f"MSG::{encoded_message}::{self.username}".encode()
            # We create a simple list for the helper function
            threading.Thread(target=self._send_tcp_data, args=(target_ip, [header]), daemon=True).start()
        else:
            print(f"User '{target_username}' not found.")
            return False
        return True
    
    # send_file is now handled by the more specific _send_file_data
    def send_file(self, target_username, filepath):
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return False

        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip, target_public_key, _ = users[target_username]
            
            aes_key = crypto_utils.generate_aes_key()
            encrypted_aes_key = crypto_utils.encrypt_with_rsa(target_public_key, aes_key)
            encoded_aes_key = base64.b64encode(encrypted_aes_key).decode('utf-8')
            
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            
            header = f"FILE::{filename}::{filesize}::{encoded_aes_key}::{self.username}".encode()

            threading.Thread(target=self._send_file_data, args=(target_ip, header, filepath, aes_key), daemon=True).start()
        else:
            print(f"User '{target_username}' not found.")
            return False
        return True

    # This is a generic helper now, only used for simple messages
    def _send_tcp_data(self, target_ip, data_list):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                for data in data_list:
                    s.sendall(data)
        except Exception as e:
            print(f"[TCP Send] Error: {e}")
            
    # This is the NEW, specific, robust function for sending files
    def _send_file_data(self, target_ip, header, filepath, aes_key):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                
                # 1. Sender sends the header
                s.sendall(header)
                
                # --- NEW STEP: THE SYNCHRONIZATION ---
                # 2. Sender now waits for the "READY" signal from the receiver
                confirmation = s.recv(1024)
                if confirmation != b"READY":
                    raise Exception("Receiver was not ready.")
                # -----------------------------------------
                
                # 3. Only after getting the signal, sender starts streaming the file
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk: break
                        encrypted_chunk = crypto_utils.encrypt_file_chunk(aes_key, chunk)
                        s.sendall(encrypted_chunk)
        except Exception as e:
            print(f"[File Send] Error: {e}")

