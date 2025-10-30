from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum
from passlib.hash import bcrypt_sha256  # safer for long passwords

Base = declarative_base()

# declare the AccessLevel Object
class AccessLevel(enum.Enum):
    ADMIN = "admin"
    GENERAL = "general"
    DORMANT = "dormant"

# declare the User Object
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    access_level = Column(Enum(AccessLevel), default=AccessLevel.GENERAL)

    # ensure this is inside the class User declaration
    def set_password(self, password: str):
        self.password_hash = bcrypt_sha256.hash(password)

    def check_password(self, password:str) -> bool:
        return bcrypt_sha256.verify(password, self.password_hash)

