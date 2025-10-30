from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.ext.declarative import declarative_base
import enum
from passlib.hash import bcrypt

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
        password = password[:71]
        self.password_hash = bcrypt.hash(password)

    def check_password(self, password:str) -> bool:
        password = password[:71]
        return bcrypt.verify(password, self.password_hash)

