from db import SessionLocal, engine
from models import Base, User, AccessLevel
from getpass import getpass

# create the tables if the don't exist, or if the website has not been ran yet
Base.metadata.create_all(bind=engine)

# create the admin user function
def create_admin():
    session = SessionLocal()
    admin_email = input("Enter admin emailL ").strip()
    # check if this admin user already exists
    existing_admin = session.query(User).filter_by(email=admin_email).first()
    if existing_admin:
        print(f"Admin {admin_email} already exists.")
        session.close()
        return
    
    # prompt for a password
    while True:
        password = getpass("Enter admin password: ")
        confirm = getpass("Confirm admin password: ")
        if password != confirm:
            print("Passwords do not match. Try again.")
        elif len(password) <8:
            print("Password too short.  Must be at least 8 characters.")
        else:
            break
    
    # Create the admin user
    admin_user = User(
        email=admin_email,
        access_level=AccessLevel.ADMIN
    )
    admin_user.set_password(password)

    session.add(admin_user)
    session.commit()
    session.close()
    print(f"Admin user {admin_email} created successfully!")
if __name__ =="__main__":
    create_admin()
