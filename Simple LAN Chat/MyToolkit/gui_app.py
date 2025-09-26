import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import queue
import time

from discovery import Discovery
from network_core import NetworkCore

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- BASIC APP SETUP ---
        self.title("Local Messenger")
        self.geometry("800x600")
        ctk.set_appearance_mode("Dark")

        # --- STATE VARIABLES ---
        self.username = ""
        self.discovery_service = None
        self.network_core = None
        self.message_queue = queue.Queue() # A thread-safe queue for messages from the network

        # --- CREATE LOGIN WINDOW ---
        self.create_login_window()

    def create_login_window(self):
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=20, padx=60, fill="both", expand=True)

        label = ctk.CTkLabel(self.login_frame, text="Enter Your Username", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=12, padx=10)

        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Username")
        self.username_entry.pack(pady=12, padx=10)
        self.username_entry.bind("<Return>", self.start_main_app) # Allow pressing Enter

        login_button = ctk.CTkButton(self.login_frame, text="Join Chat", command=self.start_main_app)
        login_button.pack(pady=12, padx=10)

    def start_main_app(self, event=None):
        username = self.username_entry.get()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty.")
            return

        self.username = username
        self.login_frame.destroy()
        self.create_main_chat_window()
        self.start_backend_services()

    def create_main_chat_window(self):
        # --- CONFIGURE GRID LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT SIDEBAR (ONLINE USERS) ---
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        
        logo_label = ctk.CTkLabel(self.sidebar_frame, text="Online Users", font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.pack(pady=20)
        
        self.user_list_frame = ctk.CTkFrame(self.sidebar_frame)
        self.user_list_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.selected_user = None

        # --- MAIN CHAT AREA ---
        self.chat_display = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.chat_display.grid(row=0, column=1, padx=20, pady=(20, 0), sticky="nsew")

        # --- MESSAGE INPUT AREA ---
        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.grid(row=1, column=1, padx=20, pady=20, sticky="ew")
        self.entry_frame.grid_columnconfigure(0, weight=1)

        self.message_entry = ctk.CTkEntry(self.entry_frame, placeholder_text="Type a message...")
        self.message_entry.grid(row=0, column=0, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message_event)

        self.send_button = ctk.CTkButton(self.entry_frame, text="Send", width=70, command=self.send_message_event)
        self.send_button.grid(row=0, column=1, padx=(10, 0))

        self.attach_button = ctk.CTkButton(self.entry_frame, text="Attach File", width=100, command=self.attach_file)
        self.attach_button.grid(row=0, column=2, padx=(10, 0))

    def start_backend_services(self):
        # Start the Discovery service
        self.discovery_service = Discovery(self.username)
        self.discovery_service.start()
        
        # Start the Network Core (TCP communication)
        self.network_core = NetworkCore(self.username, self.discovery_service, self.handle_message_received, self.handle_file_received)
        self.network_core.start()
        
        # Start the GUI update loops
        self.after(100, self.process_message_queue)
        self.after(5000, self.update_online_users)

    # --- GUI UPDATE METHODS (called from backend) ---

    def handle_message_received(self, sender, message):
        """This is a callback function called by the NetworkCore from a different thread."""
        self.message_queue.put(f"[{sender} says]: {message}\n")

    def handle_file_received(self, sender, filename, filesize, status):
        """Callback for file transfer status."""
        if status == "start":
            self.message_queue.put(f"[SYSTEM]: Receiving file '{filename}' from {sender}...\n")
        elif status == "end":
            self.message_queue.put(f"[SYSTEM]: File '{filename}' received successfully.\n")

    def process_message_queue(self):
        """Checks the queue for new messages and displays them. Runs on the GUI thread."""
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                self.chat_display.configure(state="normal")
                self.chat_display.insert("end", message)
                self.chat_display.configure(state="disabled")
                self.chat_display.see("end") # Auto-scroll
        finally:
            self.after(100, self.process_message_queue) # Reschedule

    def update_online_users(self):
        """Periodically updates the list of online users in the sidebar."""
        users = self.discovery_service.get_online_users()
        # Clear current user list
        for widget in self.user_list_frame.winfo_children():
            widget.destroy()
        
        # Add new user list
        for user, (ip, _) in users.items():
            user_button = ctk.CTkButton(self.user_list_frame, text=user, fg_color="transparent",
                                        command=lambda u=user: self.select_user(u))
            user_button.pack(fill="x", pady=2)

        self.after(5000, self.update_online_users) # Reschedule

    # --- EVENT HANDLERS (triggered by user) ---

    def select_user(self, username):
        self.selected_user = username
        self.message_entry.delete(0, "end")
        self.message_entry.insert(0, f"@{username} ")

    def send_message_event(self, event=None):
        message = self.message_entry.get()
        if not message:
            return

        if message.startswith("@") and " " in message:
            parts = message.split(" ", 1)
            target_user = parts[0][1:]
            actual_message = parts[1]
            self.network_core.send_message(target_user, actual_message)
            
            # Display our own message
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"[You to {target_user}]: {actual_message}\n")
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
            
            self.message_entry.delete(0, "end")
        else:
            messagebox.showinfo("Info", "Please select a user from the list or type '@username <message>' to send.")

    def attach_file(self):
        if not self.selected_user:
            messagebox.showinfo("Info", "Please select a user from the list to send a file to.")
            return
        
        filepath = filedialog.askopenfilename()
        if filepath:
            self.network_core.send_file(self.selected_user, filepath)
            
            # Display status in our chat
            self.chat_display.configure(state="normal")
            self.chat_display.insert("end", f"[SYSTEM]: Sending file to {self.selected_user}: {os.path.basename(filepath)}\n")
            self.chat_display.configure(state="disabled")
            self.chat_display.see("end")
            
    def on_closing(self):
        """Handle the window closing event."""
        if self.discovery_service:
            self.discovery_service.stop()
        if self.network_core:
            self.network_core.stop()
        self.destroy()

if __name__ == "__main__":
    app = ChatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
