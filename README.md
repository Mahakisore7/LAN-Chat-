# Local Messenger  

A simple **peer-to-peer local network messenger** built with Python. This application uses **UDP broadcast** for peer discovery and **TCP** for reliable message/file transfer. It allows users on the same local network to chat and share files — all without a central server.  

---

## ✨ Features  
- 🔍 **Automatic Peer Discovery** — detects online users in the local network.  
- 💬 **Direct Messaging** — send messages to a specific user.  
- 📂 **File Sharing** — send files to other users (with accept/reject option).  
- 🚪 **Graceful Exit** — allows you to leave the chat system cleanly.  

---

## ⚙️ How It Works  
- **UDP Broadcast** (Port `50000`)  
  - Used to announce presence (`online`).  
  - Periodic broadcasts ensure peers remain updated.  

- **TCP Communication** (Port `50001`)  
  - Handles reliable messaging and file transfer.  

- **User Management**  
  - Each user is identified by a **username**.  
  - Online users are stored with their IP and last active timestamp.  

---

## 🖥️ Commands  

| Command | Usage | Description |
|---------|-------|-------------|
| `list` | `list` | Show online users. |
| `msg` | `msg <user> <message>` | Send a private message. |
| `send` | `send <user> <filepath>` | Send a file to a user. |
| `exit` | `exit` | Exit the program. |

---

## 🚀 Installation & Usage  

### 1. Clone the Repository  
```bash
git clone https://github.com/<your-username>/local-messenger.git
cd local-messenger
```

### 2. Run the Program  
Make sure Python 3 is installed. Then run:  
```bash
python local_messenger.py
```

### 3. Enter Your Username  
On startup, you will be asked for a username. This is how other peers identify you.  

### 4. Start Chatting!  
- Run the program on **multiple devices in the same LAN/Wi-Fi**.  
- Use the commands to chat or send files.  

---

## 📡 Example  

**User A** starts the program with username `Alice`:  
```
Enter your username: Alice
Welcome, Alice! Your local messenger is running.
Type 'list' to see other users.
```

**User B** starts with username `Bob`:  
```
Enter your username: Bob
Welcome, Bob! Your local messenger is running.
```

Now Alice can type:  
```
msg Bob Hello Bob!
```

And Bob will see:  
```
[Message from Alice]: Hello Bob!
```

---

## ⚠️ Notes  
- Works only on **local networks (LAN/Wi-Fi)**.  
- Make sure firewalls allow UDP/TCP communication on ports `50000` and `50001`.  
- This is for **educational/demo purposes** — not secure for production.  

---

## 📜 License  
MIT License © 2025  
