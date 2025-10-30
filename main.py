from flask import Flask,request, render_template, session, redirect, url_for
from db import SessionLocal, engine
from models import Base, User
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")  # Fetch secret key from .env

# Create tables in the database if the don't exist yet
Base.metadata.create_all(bind=engine)

@app.route("/", methods=["GET", "POST"])
def index():
    db_session = SessionLocal()
    error = None
    # add code
    # initialize attempt counter if missing
    if 'attempts' not in session:
        session['attempts']= 0
    
    # if already logged in
    if session.get('user_email'):
        return render_template("index.html")
    
    # if user has exceeded 3 attempts
    if session['attempts']>=3:
        error = "Too many failed attempts.  Please try again later"
        db_session.close()
        return render_template('index.html', error=error)

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # query db to see if user exists
        user = db_session.query(User).filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_email'] = user.email
            session['attempts']=0
            db_session.close()
            return redirect(url_for("index"))
        else:
            session['attempts'] += 1
            remaining = 3 - session['attempts']
            error = f"Invalid credentials. {remaining} attempt(s) remain."
    db_session.close()
    return render_template("index.html", error=error)


@app.route("/register", methods=["GET","POST"])
def register():
    db_session = SessionLocal()
    error = None

    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        if password!=password_confirm:
            error = "Passwords do not match."
            return render_template("register.html", error=error)

        if db_session.query(User).filter_by(email=email).first():
            error = "Email already registered."
        else:
            new_user = User(email=email)
            new_user.set_password(password)
            db_session.add(new_user)
            db_session.commit()
            db_session.close()
            return redirect(url_for('index'))
    db_session.close()
    return render_template("register.html", error=error)

@app.route("/logout", methods=["POST"])
def logout():
    # Remove the user's email from the session
    session.pop('user_email', None)
    # Optionally, you can also reset attempt counters or other session data
    session.pop('attempts', None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
