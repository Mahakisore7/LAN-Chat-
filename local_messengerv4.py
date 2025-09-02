# local_messenger.py (Version 4 - GUI)

import socket
import threading
import json
import time
import os
from cryptography.fernet import Fernet, InvalidToken
import tkinter as tk
from tkinter import scrolledtext, simpledialog, filedialog, messagebox
import queue

# --- NEW: Encryption Setup ---
# 1. First, run the generate_key.py script one time.
# 2. It will print a key. PASTE THAT KEY HERE.
# 3. Every user of this chat MUST have the exact same key.
ENCRYPTION_KEY = b'EHMMCZ4s39N3MASa-DUXIc1mhpOjA5wioDmTUHVB-hg='

# Check if a valid key has been set.
if ENCRYPTION_KEY == b'PASTE_YOUR_GENERATED_KEY_HERE':
    # Using a simple GUI popup for the error
    root = tk.Tk()
    root.withdraw() # Hide the main window
    messagebox.showerror("Security Warning", "You have not set an encryption key.\nPlease run generate_key.py and paste the key into this script.")
    exit()

try:
    cipher_suite = Fernet(ENCRYPTION_KEY)
except (ValueError, TypeError):
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Key Error", "Invalid ENCRYPTION_KEY. It must be a 32-url-safe-base64-encoded key.")
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

# --- GUI Application Class ---
class ChatGUI(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.title(f"Local Messenger - {MY_USERNAME}")
        self.geometry("800x600")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # This queue will hold messages from network threads to be displayed on the GUI
        self.gui_queue = queue.Queue()

        self.build_ui()
        self.start_networking_threads()
        self.periodic_queue_check()

    def build_ui(self):
        # Main container frame
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # User list on the left
        users_frame = tk.LabelFrame(main_frame, text="Online Users", padx=5, pady=5)
        users_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        self.user_listbox = tk.Listbox(users_frame, width=25)
        self.user_listbox.pack(fill=tk.Y, expand=True)

        # Chat display and input on the right
        chat_frame = tk.Frame(main_frame)
        chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.chat_display = scrolledtext.ScrolledText(chat_frame, state='disabled', wrap=tk.WORD)
        self.chat_display.pack(fill=tk.BOTH, expand=True)

        # Input Frame
        input_frame = tk.Frame(chat_frame, height=40)
        input_frame.pack(fill=tk.X, pady=(5, 0))

        self.msg_entry = tk.Entry(input_frame)
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.msg_entry.bind("<Return>", self.send_message_event)
        
        send_button = tk.Button(input_frame, text="Send", command=self.send_message_event)
        send_button.pack(side=tk.LEFT, padx=(5,0))
        
        file_button = tk.Button(input_frame, text="Send File", command=self.send_file_event)
        file_button.pack(side=tk.LEFT, padx=(5,0))

    def start_networking_threads(self):
        # Start all our networking logic in background threads
        threads = [
            threading.Thread(target=broadcast_online_presence, daemon=True),
            threading.Thread(target=listen_for_peers, args=(self.gui_queue,), daemon=True),
            threading.Thread(target=run_tcp_server, args=(self.gui_queue,), daemon=True),
            threading.Thread(target=cleanup_inactive_users, args=(self.gui_queue,), daemon=True)
        ]
        for t in threads:
            t.start()

    def periodic_queue_check(self):
        # Check the queue for new messages from the network threads
        while not self.gui_queue.empty():
            message = self.gui_queue.get()
            
            # Update the GUI based on the message type
            if message['type'] == 'update_users':
                self.update_user_list()
            elif message['type'] == 'chat_message':
                self.display_message(f"[{message['username']}]: {message['payload']}")
            elif message['type'] == 'info_message':
                 self.display_message(f"[*] {message['payload']}", 'info')
            # --- NEW: Handle file offers from the queue ---
            elif message['type'] == 'file_offer':
                self.handle_incoming_file_offer(message)
            # --- NEW: Handle save file dialog from the queue ---
            elif message['type'] == 'save_file':
                self.save_received_file(message)
        
        # Schedule this function to run again after 100ms
        self.after(100, self.periodic_queue_check)

    def update_user_list(self):
        self.user_listbox.delete(0, tk.END)
        with lock:
            for user in sorted(online_users.keys()):
                self.user_listbox.insert(tk.END, user)
    
    def display_message(self, message, tag=None):
        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, message + "\n")
        self.chat_display.config(state='disabled')
        self.chat_display.yview(tk.END) # Auto-scroll

    def send_message_event(self, event=None):
        message_text = self.msg_entry.get().strip()
        if not message_text:
            return
        
        selected_indices = self.user_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No User Selected", "Please select a user from the list to send a message.")
            return

        username = self.user_listbox.get(selected_indices[0])
        
        # Display our own message
        self.display_message(f"[You to {username}]: {message_text}")
        
        # Send the message over the network
        threading.Thread(target=send_tcp_message, args=(username, message_text), daemon=True).start()
        
        self.msg_entry.delete(0, tk.END)

    def send_file_event(self):
        selected_indices = self.user_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No User Selected", "Please select a user from the list to send a file.")
            return
        username = self.user_listbox.get(selected_indices[0])
        
        filepath = filedialog.askopenfilename(title="Select a file to send")
        if not filepath:
            return
            
        self.display_message(f"[*] Offering to send file '{os.path.basename(filepath)}' to {username}...")
        threading.Thread(target=send_file, args=(username, filepath, self.gui_queue), daemon=True).start()

    # --- NEW: Method to handle the file offer dialog ---
    def handle_incoming_file_offer(self, offer_details):
        conn = offer_details['conn']
        username = offer_details['username']
        filename = offer_details['filename']
        filesize = offer_details['encrypted_filesize']

        if messagebox.askyesno("File Offer", f"Accept file '{filename}' ({filesize} encrypted bytes) from {username}?"):
            try:
                # 1. Send acceptance response from the main thread
                conn.send(json.dumps({"response": "accept"}).encode('utf-8'))
                self.display_message(f"[*] Accepting file '{filename}'. Downloading...")
                # 2. Start a new thread JUST for the blocking download
                threading.Thread(
                    target=download_file,
                    args=(conn, filesize, filename, self.gui_queue),
                    daemon=True
                ).start()
            except Exception as e:
                self.display_message(f"[!] Error accepting file: {e}")
                conn.close()
        else:
            try:
                # Send rejection and close the connection
                conn.send(json.dumps({"response": "reject"}).encode('utf-8'))
                self.display_message(f"[*] Rejected file transfer from {username}.")
                conn.close()
            except Exception as e:
                self.display_message(f"[!] Error rejecting file: {e}")
                conn.close()

    # --- NEW: Method to handle the save file dialog ---
    def save_received_file(self, file_details):
        filename = file_details['filename']
        decrypted_data = file_details['data']
        
        save_path = filedialog.asksaveasfilename(initialfile=filename)
        if save_path:
            try:
                with open(save_path, 'wb') as f:
                    f.write(decrypted_data)
                self.display_message(f"[*] File '{filename}' saved successfully to '{save_path}'.")
            except Exception as e:
                self.display_message(f"[!] Error saving file: {e}")
        else:
            self.display_message(f"[*] File save for '{filename}' was cancelled.")

    def on_closing(self):
        # Perform graceful shutdown
        send_broadcast(status="offline")
        time.sleep(0.5)
        self.destroy()

# --- NETWORKING LOGIC (MODIFIED FOR GUI QUEUE) ---

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

def listen_for_peers(q):
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_socket.bind(('', DISCOVERY_PORT))
    while True:
        data, addr = listen_socket.recvfrom(1024)
        message = json.loads(data.decode('utf-8'))
        username, status = message.get("username"), message.get("status")
        if not username or username == MY_USERNAME: continue
        
        with lock:
            user_changed = False
            if status == "online" and username not in online_users:
                online_users[username] = {"ip": addr[0], "last_seen": time.time()}
                user_changed = True
            elif status == "online": # Update last_seen for existing user
                 online_users[username]["last_seen"] = time.time()
            elif status == "offline" and username in online_users:
                del online_users[username]
                user_changed = True
                q.put({'type': 'info_message', 'payload': f"{username} has gone offline."})

        if user_changed:
            q.put({'type': 'update_users'})

def cleanup_inactive_users(q):
    while True:
        time.sleep(10)
        with lock:
            current_time = time.time()
            users_to_remove = [user for user, info in online_users.items() if current_time - info['last_seen'] > USER_TIMEOUT_SECONDS]
            if users_to_remove:
                for user in users_to_remove:
                    del online_users[user]
                    q.put({'type': 'info_message', 'payload': f"{user} timed out and was removed."})
                q.put({'type': 'update_users'})

def handle_client(conn, addr, q):
    handed_off = False
    try:
        header_data = conn.recv(BUFFER_SIZE)
        if not header_data: return
        
        header = json.loads(header_data.decode('utf-8'))
        msg_type = header.get("type")

        if msg_type == "message":
            encrypted_payload = header['payload'].encode('utf-8')
            decrypted_payload = cipher_suite.decrypt(encrypted_payload).decode('utf-8')
            q.put({'type': 'chat_message', 'username': header['username'], 'payload': decrypted_payload})

        elif msg_type == "file_offer":
            # --- MODIFIED: Offload UI interaction to the main thread ---
            # Pass the connection object itself in the queue
            q.put({
                'type': 'file_offer',
                'username': header['username'],
                'filename': header['filename'],
                'encrypted_filesize': header['encrypted_filesize'],
                'conn': conn
            })
            # This thread's job is now done. It will NOT close the connection.
            handed_off = True
            return

    except (InvalidToken, json.JSONDecodeError, ConnectionResetError) as e:
        q.put({'type': 'info_message', 'payload': f"Error handling client {addr}: {e}. Possible wrong encryption key."})
    finally:
        # --- MODIFIED: Only close the connection if it wasn't handed off ---
        if not handed_off:
            conn.close()

def run_tcp_server(q):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', TCP_PORT))
    server_socket.listen(5)
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr, q), daemon=True).start()

# --- NEW: Standalone function for downloading file in a background thread ---
def download_file(conn, filesize, filename, q):
    try:
        encrypted_data = b""
        while len(encrypted_data) < filesize:
            packet = conn.recv(BUFFER_SIZE)
            if not packet:
                # Connection lost prematurely
                q.put({'type': 'info_message', 'payload': f"Connection lost while downloading '{filename}'."})
                return
            encrypted_data += packet
        
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        
        # Now that we have the data, tell the main thread to open the save dialog
        q.put({
            'type': 'save_file',
            'filename': filename,
            'data': decrypted_data
        })
    except (InvalidToken, ConnectionResetError) as e:
        q.put({'type': 'info_message', 'payload': f"File download failed for '{filename}': {e}"})
    finally:
        conn.close()

def send_tcp_message(username, text):
    target_ip = online_users.get(username, {}).get('ip')
    if not target_ip: return
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((target_ip, TCP_PORT))
            encrypted_payload = cipher_suite.encrypt(text.encode('utf-8'))
            header = json.dumps({"type": "message", "username": MY_USERNAME, "payload": encrypted_payload.decode('utf-8')})
            client_socket.send(header.encode('utf-8'))
    except Exception as e:
        print(f"Error sending message: {e}") # Log to console for debugging

def send_file(username, filepath, q):
    target_ip = online_users.get(username, {}).get('ip')
    if not target_ip: return
    try:
        with open(filepath, 'rb') as f:
            file_data = f.read()
        encrypted_data = cipher_suite.encrypt(file_data)
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((target_ip, TCP_PORT))
            header = json.dumps({"type": "file_offer", "username": MY_USERNAME, "filename": os.path.basename(filepath), "encrypted_filesize": len(encrypted_data)})
            client_socket.send(header.encode('utf-8'))

            response = json.loads(client_socket.recv(1024).decode('utf-8'))
            if response.get("response") == "accept":
                q.put({'type': 'info_message', 'payload': f"{username} accepted. Sending encrypted file..."})
                client_socket.sendall(encrypted_data)
                q.put({'type': 'info_message', 'payload': f"File sent successfully."})
            else:
                q.put({'type': 'info_message', 'payload': f"{username} rejected the file."})
    except Exception as e:
        q.put({'type': 'info_message', 'payload': f"Error sending file: {e}"})

if __name__ == "__main__":
    # Use a simple dialog to ask for the username
    root = tk.Tk()
    root.withdraw() # We don't want a full GUI window, just the dialog
    MY_USERNAME = simpledialog.askstring("Username", "Please enter your username:", parent=root)
    
    if not MY_USERNAME:
        print("Username is required. Exiting.")
        exit()

    app = ChatGUI()
    app.mainloop()


# --- END OF FILE ---