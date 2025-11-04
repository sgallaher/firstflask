from sqlalchemy import Column, Integer, String, Enum, ForeignKey, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
import enum
from datetime import datetime
from passlib.hash import argon2  # modern, safe, no 72-byte limit
from sqlalchemy.orm import relationship

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
    sessions = relationship("UserSession", back_populates="user")
    # Set password using Argon2
    def set_password(self, password: str):
        self.password_hash = argon2.hash(password)

    # Check password using Argon2
    def check_password(self, password: str) -> bool:
        return argon2.verify(password, self.password_hash)


# Review model
class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    movie_id = Column(Integer, nullable=False)  # TMDb movie ID
    rating = Column(Float, nullable=False)      # rating out of 10
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="reviews")

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    login_time = Column(DateTime, default=datetime.utcnow)
    logout_time = Column(DateTime)

    user = relationship("User", back_populates="sessions")

