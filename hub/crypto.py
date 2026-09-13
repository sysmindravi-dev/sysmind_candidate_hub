import base64, hashlib
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

def _fernet():
    key=settings.APP_ENCRYPTION_KEY
    if not key:
        raw=hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        key=base64.urlsafe_b64encode(raw).decode()
    return Fernet(key.encode() if isinstance(key,str) else key)

def encrypt(value):
    if not value: return ''
    return _fernet().encrypt(value.encode()).decode()

def decrypt(value):
    if not value: return ''
    try: return _fernet().decrypt(value.encode()).decode()
    except InvalidToken: return ''
