# crypto_utils.py

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

KEYS_DIR = "keys"
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, "private_key.pem")
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, "public_key.pem")

def generate_and_save_keys():
    """
    Generates a new RSA private/public key pair if they don't exist,
    otherwise loads the existing keys from files.
    """
    if os.path.exists(PRIVATE_KEY_FILE) and os.path.exists(PUBLIC_KEY_FILE):
        print("[Crypto] Keys already exist. Loading them.")
        return load_public_key(), load_private_key()

    print("[Crypto] Generating new key pair...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    os.makedirs(KEYS_DIR, exist_ok=True)

    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    print("[Crypto] New keys generated and saved.")
    return public_key, private_key

def load_public_key():
    """Loads the public key from its file."""
    with open(PUBLIC_KEY_FILE, "rb") as f:
        return serialization.load_pem_public_key(f.read())

def load_private_key():
    """Loads the private key from its file."""
    with open(PRIVATE_KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def public_key_to_string(public_key):
    """Serializes a public key object into a string for network transmission."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

def string_to_public_key(key_string):
    """Deserializes a string back into a public key object."""
    return serialization.load_pem_public_key(key_string.encode('utf-8'))

def encrypt_message(public_key, message):
    """Encrypts a message using the recipient's public key."""
    return public_key.encrypt(
        message.encode('utf-8'),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def decrypt_message(private_key, encrypted_message):
    """Decrypts a message using the user's own private key."""
    return private_key.decrypt(
        encrypted_message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    ).decode('utf-8')

# --- NEW: Functions for Hybrid Encryption (for files) ---

def encrypt_file_data(data):
    """
    Encrypts large data using a new symmetric AES key.
    Returns the encrypted data, the AES key, and the nonce.
    """
    aes_key = AESGCM.generate_key(bit_length=128)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # GCM nonce
    encrypted_data = aesgcm.encrypt(nonce, data, None)
    return encrypted_data, aes_key, nonce

def decrypt_file_data(aes_key, nonce, encrypted_data):
    """
    Decrypts large data using a provided symmetric AES key and nonce.
    """
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, encrypted_data, None)