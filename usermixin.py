from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password,
                                method="pbkdf2:sha256")
    
    def check_password(self, password: str):
        return check_password_hash(self.password_hash, password)
    