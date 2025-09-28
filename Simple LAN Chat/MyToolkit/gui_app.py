import customtkinter as ctk
from tkinter import messagebox
import queue

from discovery import Discovery
from network_core import NetworkCore
import crypto_utils

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Secure Local Messenger")
        self.geometry("800x600")
        ctk.set_appearance_mode("Dark")

        # --- STATE & CRYPTO SETUP ---
        self.username = ""
        self.public_key, self.private_key = crypto_utils.generate_and_save_keys()
        self.discovery_service = None
        self.network_core = None
        self.message_queue = queue.Queue()
        self.selected_user = None

        self.create_login_window()

    def create_login_window(self):
        # This function remains the same
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=20, padx=60, fill="both", expand=True)
        label = ctk.CTkLabel(self.login_frame, text="Enter Your Username", font=ctk.CTkFont(size=20, weight="bold"))
        label.pack(pady=12, padx=10)
        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Username")
        self.username_entry.pack(pady=12, padx=10)
        self.username_entry.bind("<Return>", self.start_main_app)
        login_button = ctk.CTkButton(self.login_frame, text="Join Secure Chat", command=self.start_main_app)
        login_button.pack(pady=12, padx=10)

    def start_main_app(self, event=None):
        # This function remains the same
        username = self.username_entry.get()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty.")
            return
        self.username = username
        self.login_frame.destroy()
        self.create_main_chat_window()
        self.start_backend_services()

    def create_main_chat_window(self):
        # --- GUI LAYOUT SETUP ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1) # Changed row 1 to be the one that expands

        # --- LEFT SIDEBAR ---
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=3, sticky="nsew")
        logo_label = ctk.CTkLabel(self.sidebar_frame, text="Online Users", font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.pack(pady=20)
        self.user_list_frame = ctk.CTkFrame(self.sidebar_frame)
        self.user_list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # --- RIGHT CHAT AREA ---
        # NEW: A dedicated frame for the chat header
        self.chat_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_header_frame.grid(row=0, column=1, padx=20, pady=(10, 0), sticky="ew")
        
        # NEW: The label that shows who you are chatting with
        self.chatting_with_label = ctk.CTkLabel(self.chat_header_frame, text="Select a user to start chatting", anchor="w", font=ctk.CTkFont(size=16, weight="bold"))
        self.chatting_with_label.pack(side="left")

        self.chat_display = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.chat_display.grid(row=1, column=1, padx=20, pady=(10, 0), sticky="nsew")

        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.grid(row=2, column=1, padx=20, pady=20, sticky="ew")
        self.entry_frame.grid_columnconfigure(0, weight=1)

        self.message_entry = ctk.CTkEntry(self.entry_frame, placeholder_text="Type a message...")
        self.message_entry.grid(row=0, column=0, sticky="ew")
        self.message_entry.bind("<Return>", self.send_message_event)
        
        self.send_button = ctk.CTkButton(self.entry_frame, text="Send", width=70, command=self.send_message_event)
        self.send_button.grid(row=0, column=1, padx=(10, 0))

    def start_backend_services(self):
        # This function remains the same
        self.discovery_service = Discovery(self.username, self.public_key)
        self.discovery_service.start()
        
        self.network_core = NetworkCore(self.username, self.discovery_service, self.private_key, self.handle_message_received)
        self.network_core.start()
        
        self.after(100, self.process_message_queue)
        self.after(5000, self.update_online_users)

    def handle_message_received(self, sender, message):
        # This function remains the same
        self.message_queue.put(f"[{sender} says (Decrypted)]: {message}\n")

    def process_message_queue(self):
        # This function remains the same
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                self.display_message(message)
        finally:
            self.after(100, self.process_message_queue)

    def display_message(self, message):
        # This function remains the same
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", message)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def update_online_users(self):
        # This function remains the same
        users = self.discovery_service.get_online_users()
        current_buttons = {btn.cget("text").split(" ")[1]: btn for btn in self.user_list_frame.winfo_children()}
        
        online_usernames = set(users.keys())
        current_usernames = set(current_buttons.keys())

        # Add new users
        for user in online_usernames - current_usernames:
            user_button = ctk.CTkButton(self.user_list_frame, text=f"🔒 {user}", fg_color="transparent",
                                        command=lambda u=user: self.select_user(u))
            user_button.pack(fill="x", pady=2)
            
        # Remove offline users
        for user in current_usernames - online_usernames:
            current_buttons[user].destroy()
            if self.selected_user == user:
                self.select_user(None) # Clear selection if the user goes offline

        self.after(5000, self.update_online_users)

    def select_user(self, username):
        # UPDATED: More explicit logic for selecting a user
        self.selected_user = username
        if username:
            self.chatting_with_label.configure(text=f"Chatting with: {username}")
            self.message_entry.configure(state="normal")
            self.message_entry.focus()
        else:
            self.chatting_with_label.configure(text="Select a user to start chatting")
            self.message_entry.configure(state="disabled")

    def send_message_event(self, event=None):
        # UPDATED: Simpler and more robust sending logic
        message = self.message_entry.get()
        if not message:
            return
        
        # The only check we need is if a user is selected.
        if self.selected_user:
            self.network_core.send_message(self.selected_user, message)
            self.display_message(f"[You to {self.selected_user} (Encrypted)]: {message}\n")
            self.message_entry.delete(0, "end")
        else:
            messagebox.showinfo("No Recipient", "Please select a user from the online list before sending a message.")
            
    def on_closing(self):
        # This function remains the same
        if self.discovery_service: self.discovery_service.stop()
        if self.network_core: self.network_core.stop()
        self.destroy()

if __name__ == "__main__":
    app = ChatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

