# local_messenger.py (Version 3 - Encrypted)

import socket
import threading
import json
import time
import os
from cryptography.fernet import Fernet, InvalidToken

# --- NEW: Encryption Setup ---
# 1. First, run the generate_key.py script one time.
# 2. It will print a key. PASTE THAT KEY HERE.
# 3. Every user of this chat MUST have the exact same key.
ENCRYPTION_KEY = b'EHMMCZ4s39N3MASa-DUXIc1mhpOjA5wioDmTUHVB-hg='

# Check if a valid key has been set.
if ENCRYPTION_KEY == b'PASTE_YOUR_GENERATED_KEY_HERE':
    print("!!! SECURITY WARNING !!!")
    print("You have not set an encryption key.")
    print("Please run generate_key.py and paste the key into this script.")
    exit()

try:
    cipher_suite = Fernet(ENCRYPTION_KEY)
except (ValueError, TypeError):
    print("!!! ERROR: Invalid ENCRYPTION_KEY. It must be a 32-url-safe-base64-encoded key.")
    exit()


# --- Configuration ---
DISCOVERY_PORT = 50000
TCP_PORT = 50001
BUFFER_SIZE = 4096
MY_USERNAME = ""
USER_TIMEOUT_SECONDS = 15 

# --- Shared Data Structures ---
online_users = {}
lock = threading.Lock()

# --- Peer Discovery (UDP - Unencrypted) ---

def send_broadcast(status="online"):
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = json.dumps({"username": MY_USERNAME, "status": status})
    broadcast_socket.sendto(message.encode('utf-8'), ('<broadcast>', DISCOVERY_PORT))
    broadcast_socket.close()

def broadcast_online_presence():
    while True:
        send_broadcast(status="online")
        time.sleep(5)

def listen_for_peers():
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_socket.bind(('', DISCOVERY_PORT))
    while True:
        data, addr = listen_socket.recvfrom(1024)
        message = json.loads(data.decode('utf-8'))
        username, status = message.get("username"), message.get("status")
        if not username or username == MY_USERNAME: continue
        with lock:
            if status == "online":
                online_users[username] = {"ip": addr[0], "last_seen": time.time()}
            elif status == "offline" and username in online_users:
                del online_users[username]
                print(f"\n[*] {username} has gone offline.\n> ", end="")

def cleanup_inactive_users():
    while True:
        time.sleep(10)
        with lock:
            current_time = time.time()
            users_to_remove = [user for user, info in online_users.items() if current_time - info['last_seen'] > USER_TIMEOUT_SECONDS]
            for user in users_to_remove:
                del online_users[user]
                print(f"\n[*] {user} timed out and was removed.\n> ", end="")

# --- Reliable Communication (TCP - Encrypted) ---

def handle_client(conn, addr):
    print(f"\n[+] Accepted connection from {addr[0]}:{addr[1]}")
    try:
        header_data = conn.recv(BUFFER_SIZE)
        if not header_data: return
        
        header = json.loads(header_data.decode('utf-8'))
        msg_type = header.get("type")

        if msg_type == "message":
            encrypted_payload = header['payload'].encode('utf-8')
            decrypted_payload = cipher_suite.decrypt(encrypted_payload).decode('utf-8')
            print(f"\n[Message from {header['username']}]: {decrypted_payload}\n> ", end="")

        elif msg_type == "file_offer":
            filename, encrypted_filesize = header['filename'], header['encrypted_filesize']
            print(f"\n[File offer from {header['username']}]: {filename} ({encrypted_filesize} encrypted bytes).")
            user_input = input("Accept? (y/n): ").lower()
            
            if user_input == 'y':
                conn.send(json.dumps({"response": "accept"}).encode('utf-8'))
                
                encrypted_data = b""
                while len(encrypted_data) < encrypted_filesize:
                    packet = conn.recv(BUFFER_SIZE)
                    if not packet: break
                    encrypted_data += packet
                
                decrypted_data = cipher_suite.decrypt(encrypted_data)
                with open(filename, 'wb') as f:
                    f.write(decrypted_data)
                print(f"\n[+] File '{filename}' received successfully.\n> ", end="")
            else:
                conn.send(json.dumps({"response": "reject"}).encode('utf-8'))
                print("\n[-] File transfer rejected.\n> ", end="")

    except (InvalidToken, json.JSONDecodeError, ConnectionResetError) as e:
        print(f"\n[!] Error handling client {addr}: {e}. Possible wrong encryption key.")
    finally:
        conn.close()

def run_tcp_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', TCP_PORT))
    server_socket.listen(5)
    print(f"[*] TCP Server listening on port {TCP_PORT}")
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

# --- User Interface (CLI) & Main Execution ---

def send_tcp_message(username, text):
    target_ip = online_users.get(username, {}).get('ip')
    if not target_ip:
        print(f"[!] User '{username}' not found or offline.")
        return
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((target_ip, TCP_PORT))
            encrypted_payload = cipher_suite.encrypt(text.encode('utf-8'))
            header = json.dumps({
                "type": "message", "username": MY_USERNAME, "payload": encrypted_payload.decode('utf-8')
            })
            client_socket.send(header.encode('utf-8'))
    except Exception as e:
        print(f"[!] Error sending message to {username}: {e}")

def send_file(username, filepath):
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}")
        return

    target_ip = online_users.get(username, {}).get('ip')
    if not target_ip:
        print(f"[!] User '{username}' not found or offline.")
        return
        
    try:
        with open(filepath, 'rb') as f:
            file_data = f.read()
        encrypted_data = cipher_suite.encrypt(file_data)
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((target_ip, TCP_PORT))
            header = json.dumps({
                "type": "file_offer", "username": MY_USERNAME,
                "filename": os.path.basename(filepath), "encrypted_filesize": len(encrypted_data)
            })
            client_socket.send(header.encode('utf-8'))

            response = json.loads(client_socket.recv(1024).decode('utf-8'))
            if response.get("response") == "accept":
                print(f"[*] {username} accepted. Sending encrypted file...")
                client_socket.sendall(encrypted_data)
                print(f"[*] File '{os.path.basename(filepath)}' sent successfully.")
            else:
                print(f"[-] {username} rejected the file.")
    except Exception as e:
        print(f"[!] Error sending file to {username}: {e}")

def cli_input_loop():
    while True:
        cmd_input = input("> ")
        parts = cmd_input.split()
        if not parts: continue
        
        command = parts[0].lower()

        if command == "list":
            print("\n--- Online Users ---")
            with lock:
                if not online_users: print("No other users found.")
                for user, info in online_users.items(): print(f"- {user} (at {info['ip']})")
            print("--------------------\n")

        elif command == "msg" and len(parts) >= 3:
            username = parts[1]
            if username == MY_USERNAME: print("[!] You cannot send a message to yourself."); continue
            send_tcp_message(username, " ".join(parts[2:]))
        
        elif command == "bcast" and len(parts) >= 2:
            message_text = " ".join(parts[1:])
            print("[*] Sending broadcast message...")
            with lock:
                for user in online_users: send_tcp_message(user, f"(Broadcast) {message_text}")

        elif command == "send" and len(parts) == 3:
            username, filepath = parts[1], parts[2]
            if username == MY_USERNAME: print("[!] You cannot send a file to yourself."); continue
            send_file(username, filepath)

        elif command == "exit":
            print("Sending goodbye message..."); send_broadcast(status="offline"); time.sleep(0.5)
            print("Exiting..."); os._exit(0)
        else:
            print("Unknown command. Try: list, msg, bcast, send, exit")

if __name__ == "__main__":
    MY_USERNAME = input("Enter your username: ")

    threads = [
        threading.Thread(target=broadcast_online_presence, daemon=True),
        threading.Thread(target=listen_for_peers, daemon=True),
        threading.Thread(target=run_tcp_server, daemon=True),
        threading.Thread(target=cleanup_inactive_users, daemon=True)
    ]
    for t in threads:
        t.start()
    
    print(f"\nWelcome, {MY_USERNAME}! Your local messenger is running.")
    print("--- This messenger is using end-to-end encryption. ---")
    print("Commands: list, msg <user> <message>, bcast <message>, send <user> <filepath>, exit\n")

    cli_input_loop()
