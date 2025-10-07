# gui_app.py

import customtkinter as ctk
from tkinter import messagebox, filedialog
import queue
import os

from discovery import Discovery
from network_core import NetworkCore
import crypto_utils

class ChatApp(ctk.CTk):
    def __init__(self):
        """
        Initialize the main chat application window.
        Sets up keys, event queue, and launches the login window.
        """
        super().__init__()
        self.title("Secure Local Messenger")
        self.geometry("800x600")
        ctk.set_appearance_mode("Dark")

        self.username = ""
        # Generate and load RSA key pair for encryption/decryption
        self.public_key, self.private_key = crypto_utils.generate_and_save_keys()
        self.discovery_service = None
        self.network_core = None
        self.event_queue = queue.Queue()  # Thread-safe queue for GUI events
        self.selected_user = None

        self.create_login_window()

    def create_login_window(self):
        """
        Create the initial login window for username entry.
        """
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=20, padx=60, fill="both", expand=True)
        label = ctk.CTkLabel(self.login_frame, text="Enter Your Username", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=12, padx=10)
        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Username")
        self.username_entry.pack(pady=12, padx=10)
        self.username_entry.bind("<Return>", self.start_main_app)  # Allow pressing Enter to submit
        login_button = ctk.CTkButton(self.login_frame, text="Join Secure Chat", command=self.start_main_app)
        login_button.pack(pady=12, padx=10)

    def start_main_app(self, event=None):
        """
        Start the main chat application after username is entered.
        Destroys login window, creates chat window, and starts backend services.
        """
        username = self.username_entry.get()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty.")
            return
        self.username = username
        self.login_frame.destroy()
        self.create_main_chat_window()
        self.start_backend_services()

    def create_main_chat_window(self):
        """
        Set up the main chat window layout, including sidebar, chat display, and entry widgets.
        """
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Sidebar for online users
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=3, sticky="nsew")
        logo_label = ctk.CTkLabel(self.sidebar_frame, text="Online Users", font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.pack(pady=20)
        self.user_list_frame = ctk.CTkFrame(self.sidebar_frame)
        self.user_list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Header showing current chat recipient
        self.chat_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_header_frame.grid(row=0, column=1, padx=20, pady=(10, 0), sticky="ew")
        self.chatting_with_label = ctk.CTkLabel(self.chat_header_frame, text="Select a user to start chatting", anchor="w", font=ctk.CTkFont(size=16, weight="bold"))
        self.chatting_with_label.pack(side="left")

        # Chat display area
        self.chat_display = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.chat_display.grid(row=1, column=1, padx=20, pady=(10, 0), sticky="nsew")

        # Entry area for messages and file attachment
        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.grid(row=2, column=1, padx=20, pady=20, sticky="ew")
        self.entry_frame.grid_columnconfigure(1, weight=1)

        self.attach_button = ctk.CTkButton(self.entry_frame, text="📎", width=40, command=self.attach_file)
        self.attach_button.grid(row=0, column=0, sticky="w")
        self.message_entry = ctk.CTkEntry(self.entry_frame, placeholder_text="Type a message...")
        self.message_entry.grid(row=0, column=1, padx=(10, 10), sticky="ew")
        self.message_entry.bind("<Return>", self.send_event)
        
        self.send_button = ctk.CTkButton(self.entry_frame, text="Send", width=70, command=self.send_event)
        self.send_button.grid(row=0, column=2, sticky="e")

    def start_backend_services(self):
        """
        Start the discovery and network core services for peer discovery and communication.
        Schedule periodic updates for event processing and online user list.
        """
        self.discovery_service = Discovery(self.username, self.public_key)
        self.network_core = NetworkCore(self.username, self.discovery_service, self.private_key, self.handle_message_received, self.handle_file_event)
        self.discovery_service.start()
        self.network_core.start()
        self.after(100, self.process_event_queue)      # Process events every 100ms
        self.after(5000, self.update_online_users)     # Update online users every 5s

    def handle_message_received(self, sender, message):
        """
        Callback for when a message is received from the network core.
        Adds the message to the event queue for display.
        """
        self.event_queue.put(("message", f"[{sender} says (Decrypted)]: {message}\n"))
        
    def handle_file_event(self, event_type, sender, filename):
        """
        Callback for file transfer events (start/end).
        Adds info messages to the event queue for display.
        """
        if event_type == "start":
            self.event_queue.put(("info", f"[System] Receiving file '{filename}' from {sender}...\n"))
        elif event_type == "end":
            self.event_queue.put(("info", f"[System] File '{filename}' from {sender} received successfully!\n"))

    def process_event_queue(self):
        """
        Periodically process events from the event queue and display them in the chat window.
        """
        try:
            while not self.event_queue.empty():
                event_type, message = self.event_queue.get_nowait()
                self.display_message(message)
        finally:
            self.after(100, self.process_event_queue)  # Schedule next check

    def display_message(self, message):
        """
        Display a message in the chat display area.
        """
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", message)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def update_online_users(self):
        """
        Periodically update the list of online users in the sidebar.
        Adds new users, removes offline users, and updates selection.
        """
        users = self.discovery_service.get_online_users()
        current_buttons = {btn.cget("text").split(" ")[1]: btn for btn in self.user_list_frame.winfo_children()}
        online_usernames = set(users.keys())
        current_usernames = set(current_buttons.keys())

        # Add new user buttons
        for user in online_usernames - current_usernames:
            user_button = ctk.CTkButton(self.user_list_frame, text=f"🔒 {user}", fg_color="transparent", command=lambda u=user: self.select_user(u))
            user_button.pack(fill="x", pady=2)
            
        # Remove buttons for users who went offline
        for user in current_usernames - online_usernames:
            current_buttons[user].destroy()
            if self.selected_user == user: self.select_user(None)

        self.after(5000, self.update_online_users)  # Schedule next update

    def select_user(self, username):
        """
        Select a user to chat with.
        Updates the chat header and enables/disables message entry accordingly.
        """
        self.selected_user = username
        if username:
            self.chatting_with_label.configure(text=f"Chatting with: {username}")
            self.message_entry.configure(state="normal")
            self.message_entry.focus()
        else:
            self.chatting_with_label.configure(text="Select a user to start chatting")
            self.message_entry.configure(state="disabled")

    def send_event(self, event=None):
        """
        Send a message to the selected user.
        Displays the sent message and clears the entry field.
        """
        message = self.message_entry.get()
        if not self.selected_user:
            messagebox.showinfo("No Recipient", "Please select a user to send a message or file.")
            return

        if message:
            if self.network_core.send_message(self.selected_user, message):
                self.display_message(f"[You to {self.selected_user} (Encrypted)]: {message}\n")
            self.message_entry.delete(0, "end")
            
    def attach_file(self):
        """
        Open a file dialog to select a file and send it to the selected user.
        Displays status messages and error handling.
        """
        if not self.selected_user:
            messagebox.showinfo("No Recipient", "Please select a user to send a file to.")
            return
            
        filepath = filedialog.askopenfilename()
        if filepath:
            self.display_message(f"[System] Sending file '{os.path.basename(filepath)}' to {self.selected_user}...\n")
            if not self.network_core.send_file(self.selected_user, filepath):
                messagebox.showerror("Error", "Failed to send file.")
            
    def on_closing(self):
        """
        Cleanly stop backend services and close the application window.
        """
        if self.discovery_service: self.discovery_service.stop()
        if self.network_core: self.network_core.stop()
        self.destroy()

if __name__ == "__main__":
    # Entry point for the application
    app = ChatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()