from cryptography.fernet import Fernet
import base64
import os
from dotenv import load_dotenv

load_dotenv()
# Generate a secret key (only once, store securely)

secret_key = os.getenv("SECRET_KEY")
print(secret_key)
cipher = Fernet(secret_key)

class Cryption:
    @staticmethod
    def encrypt_token(token: str) -> str:
        return cipher.encrypt(token.encode()).decode()

    @staticmethod
    def decrypt_token(encrypted_token: str) -> str:
        return cipher.decrypt(encrypted_token.encode()).decode()

cryption = Cryption()
