from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum
from passlib.hash import argon2  # modern, safe, no 72-byte limit

Base = declarative_base()

# Access level enum
class AccessLevel(enum.Enum):
    ADMIN = "admin"
    GENERAL = "general"
    DORMANT = "dormant"

# User model
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    access_level = Column(Enum(AccessLevel), default=AccessLevel.GENERAL)

    # Set password using Argon2
    def set_password(self, password: str):
        self.password_hash = argon2.hash(password)

    # Check password using Argon2
    def check_password(self, password: str) -> bool:
        return argon2.verify(password, self.password_hash)
