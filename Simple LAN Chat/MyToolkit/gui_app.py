import customtkinter as ctk
from tkinter import messagebox, filedialog
import queue
import uuid
from PIL import Image
import os
from discovery import Discovery
from network_core import NetworkCore
import crypto_utils

# NEW: A widget for a single message in the chat display
class MessageWidget(ctk.CTkFrame):
    def __init__(self, master, sender, message, is_own_message=False):
        super().__init__(master, fg_color="transparent")
        
        self.status_label = ctk.CTkLabel(self, text="Sent", font=ctk.CTkFont(size=10), text_color="gray")
        
        if is_own_message:
            # Your own messages align to the right
            label = ctk.CTkLabel(self, text=f"[You]: {message}", wraplength=400, justify="right", fg_color="#2b59da", corner_radius=10, text_color="white")
            label.pack(side="right", pady=2, padx=10, ipady=5, ipadx=5)
            self.status_label.pack(side="right", padx=(0, 10))
            self.pack(fill="x", anchor="e", pady=2, padx=10)
        else:
            # Others' messages align to the left
            label = ctk.CTkLabel(self, text=f"[{sender}]: {message}", wraplength=400, justify="left", fg_color="#4d4d4d", corner_radius=10, text_color="white")
            label.pack(side="left", pady=2, padx=10, ipady=5, ipadx=5)
            self.pack(fill="x", anchor="w", pady=2, padx=10)

    def update_status(self, status):
        self.status_label.configure(text=status)


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
        
        # NEW: Dictionary to track message widgets by ID for status updates
        self.message_widgets = {}
        # NEW: Store user profile pictures
        self.user_pfp = {}

        self.create_login_window()

    def create_login_window(self):
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
        username = self.username_entry.get()
        if not username:
            messagebox.showerror("Error", "Username cannot be empty.")
            return
        self.username = username
        self.login_frame.destroy()
        self.create_main_chat_window()
        self.start_backend_services()

    def create_main_chat_window(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=3, sticky="nsew")
        
        logo_label = ctk.CTkLabel(self.sidebar_frame, text="Online Users", font=ctk.CTkFont(size=20, weight="bold"))
        logo_label.pack(pady=20)
        
        self.user_list_frame = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="")
        self.user_list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # NEW: Profile picture selection button
        pfp_button = ctk.CTkButton(self.sidebar_frame, text="Set Profile Pic", command=self.set_profile_picture)
        pfp_button.pack(pady=10, padx=10)
        self.my_pfp_label = ctk.CTkLabel(self.sidebar_frame, text="")
        self.my_pfp_label.pack(pady=5)


        self.chat_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_header_frame.grid(row=0, column=1, padx=20, pady=(10, 0), sticky="ew")
        
        self.chatting_with_label = ctk.CTkLabel(self.chat_header_frame, text="Select a user to start chatting", anchor="w", font=ctk.CTkFont(size=16, weight="bold"))
        self.chatting_with_label.pack(side="left")

        # UPDATED: Chat display is now a scrollable frame
        self.chat_display_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.chat_display_frame.grid(row=1, column=1, padx=20, pady=(10, 0), sticky="nsew")

        self.entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.entry_frame.grid(row=2, column=1, padx=20, pady=20, sticky="ew")
        self.entry_frame.grid_columnconfigure(0, weight=1)

        # NEW: Send File button
        self.send_file_button = ctk.CTkButton(self.entry_frame, text="📎", width=30, command=self.send_file_event)
        self.send_file_button.grid(row=0, column=0, sticky="w")

        self.message_entry = ctk.CTkEntry(self.entry_frame, placeholder_text="Type a message...")
        self.message_entry.grid(row=0, column=1, sticky="ew", padx=10)
        self.message_entry.bind("<Return>", self.send_message_event)
        
        self.send_button = ctk.CTkButton(self.entry_frame, text="Send", width=70, command=self.send_message_event)
        self.send_button.grid(row=0, column=2)
        # Re-column configure for new button
        self.entry_frame.grid_columnconfigure(1, weight=1)

    def start_backend_services(self):
        self.discovery_service = Discovery(self.username, self.public_key)
        self.discovery_service.start()
        
        # UPDATED: Pass the new callbacks to NetworkCore
        self.network_core = NetworkCore(self.username, self.discovery_service, self.private_key, 
                                        self.handle_message_received, self.handle_ack_received, self.handle_file_received)
        self.network_core.start()
        
        self.after(100, self.process_message_queue)
        self.after(5000, self.update_online_users)

    def handle_message_received(self, sender, message):
        self.message_queue.put(("MSG", sender, message))

    # NEW: Handle incoming ACKs
    def handle_ack_received(self, msg_id):
        self.message_queue.put(("ACK", msg_id))

    # NEW: Handle incoming files
    def handle_file_received(self, sender, filename):
        self.message_queue.put(("FILE", sender, f"Received file '{filename}' from {sender}"))

    def process_message_queue(self):
        try:
            while not self.message_queue.empty():
                item = self.message_queue.get_nowait()
                msg_type = item[0]

                if msg_type == "MSG":
                    _, sender, message = item
                    self.display_message(sender, message, is_own=False)
                elif msg_type == "ACK":
                    _, msg_id = item
                    if msg_id in self.message_widgets:
                        self.message_widgets[msg_id].update_status("Delivered")
                elif msg_type == "FILE":
                    _, sender, message = item
                    self.display_message(sender, message, is_own=False)

        finally:
            self.after(100, self.process_message_queue)

    def display_message(self, sender, message, is_own=False, msg_id=None):
        widget = MessageWidget(self.chat_display_frame, sender, message, is_own_message=is_own)
        if msg_id:
            self.message_widgets[msg_id] = widget
        # Auto-scroll to the bottom
        self.after(50, self.chat_display_frame._parent_canvas.yview_moveto, 1.0)


    def update_online_users(self):
        users = self.discovery_service.get_online_users()
        current_buttons = {btn.cget("text"): btn for btn in self.user_list_frame.winfo_children()}
        
        online_usernames = set(users.keys())
        current_usernames = set(current_buttons.keys())

        for user in online_usernames - current_usernames:
            user_button = ctk.CTkButton(self.user_list_frame, text=user, fg_color="transparent",
                                        anchor="w", command=lambda u=user: self.select_user(u))
            user_button.pack(fill="x", pady=2, padx=5)
            
        for user in current_usernames - online_usernames:
            current_buttons[user].destroy()
            if self.selected_user == user:
                self.select_user(None)

        self.after(5000, self.update_online_users)

    def select_user(self, username):
        self.selected_user = username
        if username:
            self.chatting_with_label.configure(text=f"Chatting with: {username}")
            self.message_entry.configure(state="normal")
            self.message_entry.focus()
        else:
            self.chatting_with_label.configure(text="Select a user to start chatting")
            self.message_entry.configure(state="disabled")

    def send_message_event(self, event=None):
        message = self.message_entry.get()
        if not message or not self.selected_user:
            return
        
        msg_id = self.network_core.send_message(self.selected_user, message)
        if msg_id:
            self.display_message(self.username, message, is_own=True, msg_id=msg_id)
            self.message_entry.delete(0, "end")
        else:
            messagebox.showerror("Error", f"Could not send message to {self.selected_user}.")
            
    # NEW: Send File Event
    def send_file_event(self):
        if not self.selected_user:
            messagebox.showinfo("No Recipient", "Please select a user to send a file to.")
            return
        
        filepath = filedialog.askopenfilename()
        if filepath:
            self.network_core.send_file(self.selected_user, filepath)
            self.display_message(self.username, f"Sent file: {os.path.basename(filepath)}", is_own=True)

    # NEW: Set Profile Picture Event
    def set_profile_picture(self):
        filepath = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif")])
        if filepath:
            # For simplicity, we'll just display it locally. 
            # Broadcasting/requesting profile pictures requires updating the discovery and network protocols.
            try:
                img = Image.open(filepath)
                img.thumbnail((48, 48))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(48, 48))
                self.my_pfp_label.configure(image=ctk_img)
                messagebox.showinfo("Success", "Profile picture updated locally.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")

    def on_closing(self):
        if self.discovery_service: self.discovery_service.stop()
        if self.network_core: self.network_core.stop()
        self.destroy()

if __name__ == "__main__":
    app = ChatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()