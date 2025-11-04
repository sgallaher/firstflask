from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from db import SessionLocal, engine
from models import Base, User, Review, UserSession, AccessLevel
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta
from sqlalchemy import func

from functools import wraps

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")  # Fetch secret key from .env
app.permanent_session_lifetime = timedelta(hours=1)  # session expires after 1 hour

# Create tables in the database if they don't exist yet
Base.metadata.create_all(bind=engine)


@app.before_request
def check_session_expiry():
    """Clear session if expired."""
    if 'start_time' in session:
        start_time = datetime.fromisoformat(session['start_time'])
        if datetime.utcnow() - start_time > timedelta(hours=1):
            session.clear()

@app.route("/", methods=["GET", "POST"])
def index():
    db_session = SessionLocal()
    error = None

    # Initialize attempt counter if missing
    if 'attempts' not in session:
        session['attempts'] = 0

    # Handle login POST
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = db_session.query(User).filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_email'] = user.email
            session['attempts'] = 0

            # Redirect admin users directly to dashboard
            if user.access_level == AccessLevel.ADMIN:
                db_session.close()
                return redirect(url_for("admin_dashboard"))

            db_session.close()
            return redirect(url_for("index"))
        else:
            session['attempts'] += 1
            remaining = 3 - session['attempts']
            error = f"Invalid credentials. {remaining} attempt(s) remain."

    # If user is logged in
    if session.get("user_email"):
        user = db_session.query(User).filter_by(email=session['user_email']).first()
        # Redirect admin directly
        if user and user.access_level == AccessLevel.ADMIN:
            db_session.close()
            return redirect(url_for("admin_dashboard"))

        # Regular user: fetch their reviews (existing logic)
        user_reviews = []
        for review in user.reviews:
            avg_rating = db_session.query(func.avg(Review.rating))\
                .filter(Review.movie_id == review.movie_id).scalar()
            avg_rating = round(avg_rating, 2) if avg_rating else None

            movie_details = {}
            cast_list = []
            try:
                r = requests.get(
                    f"https://api.themoviedb.org/3/movie/{review.movie_id}",
                    params={"api_key": os.getenv("TMDB_API_KEY"), "language": "en-US"}
                )
                if r.status_code == 200:
                    data = r.json()
                    movie_details = {
                        "title": data.get("title"),
                        "poster_path": data.get("poster_path"),
                        "overview": data.get("overview"),
                        "genres": data.get("genres", []),
                        "runtime": data.get("runtime"),
                        "release_date": data.get("release_date")
                    }
                # Fetch cast
                credits_resp = requests.get(
                    f"https://api.themoviedb.org/3/movie/{review.movie_id}/credits",
                    params={"api_key": os.getenv("TMDB_API_KEY")}
                )
                if credits_resp.status_code == 200:
                    cast_list = [c['name'] for c in credits_resp.json().get('cast', [])[:10]]
            except Exception as e:
                print(f"TMDB fetch error: {e}")

            user_reviews.append({
                "movie_id": review.movie_id,
                "rating": review.rating,
                "avg_rating": avg_rating,
                "timestamp": review.timestamp,
                "title": movie_details.get("title"),
                "poster_path": movie_details.get("poster_path"),
                "movie_details": movie_details,
                "main_cast": cast_list
            })
        db_session.close()
        return render_template("index.html", error=error, user_reviews=user_reviews)

    db_session.close()
    return render_template("index.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    db_session = SessionLocal()
    user_session_id = session.get("user_session_id")

    if user_session_id:
        user_session = db_session.query(UserSession).filter_by(id=user_session_id).first()
        if user_session:
            user_session.logout_time = datetime.utcnow()
            db_session.commit()

    db_session.close()
    session.clear()
    return redirect(url_for("index"))



# --- Admin decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('index'))
        db_session = SessionLocal()
        user = db_session.query(User).filter_by(email=session['user_email']).first()
        db_session.close()
        if not user or user.access_level != AccessLevel.ADMIN:
            return "Access denied: Admins only", 403
        return f(*args, **kwargs)
    return decorated_function

# --- Admin dashboard route ---
@app.route("/admin")
@admin_required
def admin_dashboard():
    db_session = SessionLocal()
    users = db_session.query(User).all()
    user_data = []

    for user in users:
        total_reviews = db_session.query(Review).filter_by(user_id=user.id).count()
        avg_review = db_session.query(func.avg(Review.rating)).filter_by(user_id=user.id).scalar()
        avg_review = round(avg_review, 2) if avg_review else None

        user_data.append({
            "id": user.id,
            "email": user.email,
            "total_reviews": total_reviews,
            "avg_review": avg_review
        })

    db_session.close()
    return render_template("admin_dashboard.html", users=user_data)

# --- Admin user details route ---
@app.route("/admin/user/<int:user_id>")
@admin_required
def admin_user_details(user_id):
    db_session = SessionLocal()
    user = db_session.query(User).filter_by(id=user_id).first()
    if not user:
        db_session.close()
        return "User not found", 404

    # Fetch all reviews for this user
    user_reviews = []
    genre_ratings = {}  # genre -> list of ratings

    for review in user.reviews:
        movie_details = {}
        main_genres = []

        # Get movie details from TMDb
        try:
            r = requests.get(
                f"https://api.themoviedb.org/3/movie/{review.movie_id}",
                params={"api_key": os.getenv("TMDB_API_KEY"), "language": "en-US"}
            )
            if r.status_code == 200:
                data = r.json()
                movie_details = {
                    "title": data.get("title"),
                    "poster_path": data.get("poster_path"),
                    "release_date": data.get("release_date"),
                    "overview": data.get("overview"),
                    "genres": [g['name'] for g in data.get('genres', [])]
                }
                main_genres = movie_details['genres']
        except Exception as e:
            print(f"TMDB fetch error: {e}")

        # Aggregate genre ratings
        for genre in main_genres:
            if genre not in genre_ratings:
                genre_ratings[genre] = []
            genre_ratings[genre].append(review.rating)

        user_reviews.append({
            "movie_id": review.movie_id,
            "rating": review.rating,
            "timestamp": review.timestamp,
            "movie_details": movie_details
        })

    # Calculate average rating per genre
    genre_avg = {}
    for genre, ratings in genre_ratings.items():
        genre_avg[genre] = round(sum(ratings)/len(ratings), 2)

    # Determine favorite genre (highest average rating)
    favorite_genre = max(genre_avg, key=genre_avg.get) if genre_avg else None

    db_session.close()
    return render_template(
        "admin_user_details.html",
        user=user,
        user_reviews=user_reviews,
        genre_avg=genre_avg,
        favorite_genre=favorite_genre
    )


@app.route("/register", methods=["GET","POST"])
def register():
    db_session = SessionLocal()
    error = None

    if request.method == "POST":
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('password_confirm')
        if password != password_confirm:
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


@app.route("/search", methods=["GET", "POST"])
def search():
    results = []
    error = None
    genres = []

    tmdb_key = os.getenv("TMDB_API_KEY")

    # Fetch genres for dropdown
    genre_url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={tmdb_key}&language=en-US"
    r = requests.get(genre_url)
    if r.status_code == 200:
        genres = r.json().get("genres", [])

    # Determine page from GET parameter, default = 1
    page = request.args.get("page", 1, type=int)

    if request.method == "POST" or request.args.get("search"):
        title_query = request.form.get("query") or request.args.get("query")
        actor_name = request.form.get("actor_name") or request.args.get("actor_name")
        genre_id = request.form.get("genre") or request.args.get("genre")
        year_from = request.form.get("year_from") or request.args.get("year_from")
        year_to = request.form.get("year_to") or request.args.get("year_to")

        base_url = "https://api.themoviedb.org/3/discover/movie"
        params = {
            "api_key": tmdb_key,
            "language": "en-US",
            "sort_by": "popularity.desc",
            "page": page,
        }

        # Case 1: Actor search
        if actor_name:
            actor_search_url = "https://api.themoviedb.org/3/search/person"
            r_actor = requests.get(actor_search_url, params={"api_key": tmdb_key, "query": actor_name})
            if r_actor.status_code == 200 and r_actor.json().get("results"):
                actor_id = r_actor.json()["results"][0]["id"]
                params["with_cast"] = actor_id
                if genre_id:
                    params["with_genres"] = genre_id
                if year_from:
                    params["primary_release_date.gte"] = f"{year_from}-01-01"
                if year_to:
                    params["primary_release_date.lte"] = f"{year_to}-12-31"

                r_movies = requests.get(base_url, params=params)
                if r_movies.status_code == 200:
                    data = r_movies.json()
                    results = data.get("results", [])
                    total_pages = data.get("total_pages", 1)
                else:
                    error = "Could not fetch movies for this actor."
            else:
                error = "Actor not found."

        # Case 2: Movie title search
        elif title_query:
            search_url = "https://api.themoviedb.org/3/search/movie"
            r_title = requests.get(search_url, params={
                "api_key": tmdb_key,
                "query": title_query,
                "language": "en-US",
                "page": page,
                "include_adult": False
            })
            if r_title.status_code == 200:
                data = r_title.json()
                results = data.get("results", [])
                total_pages = data.get("total_pages", 1)
            else:
                error = "Error fetching movie data."

        # Case 3: Only filters
        else:
            if genre_id:
                params["with_genres"] = genre_id
            if year_from:
                params["primary_release_date.gte"] = f"{year_from}-01-01"
            if year_to:
                params["primary_release_date.lte"] = f"{year_to}-12-31"

            r_filters = requests.get(base_url, params=params)
            if r_filters.status_code == 200:
                data = r_filters.json()
                results = data.get("results", [])
                total_pages = data.get("total_pages", 1)
            else:
                error = "Error fetching movies."

        # Fetch main cast for each movie (top 5 actors)
        for movie in results:
            movie_id = movie['id']
            credits_url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits"
            r_credits = requests.get(credits_url, params={"api_key": tmdb_key})
            if r_credits.status_code == 200:
                cast = r_credits.json().get("cast", [])
                movie['main_cast'] = [c['name'] for c in cast[:5]]
            else:
                movie['main_cast'] = []

        # Keep search parameters for pagination
        search_params = {
            "query": title_query or "",
            "actor_name": actor_name or "",
            "genre": genre_id or "",
            "year_from": year_from or "",
            "year_to": year_to or "",
            "search": 1
        }

        return render_template(
            "search.html",
            results=results,
            genres=genres,
            error=error,
            page=page,
            total_pages=total_pages,
            search_params=search_params
        )

    return render_template("search.html", results=results, genres=genres, error=error,
                           page=1, total_pages=1, search_params={})


@app.route("/review", methods=["POST"])
def review():
    if not session.get("user_email"):
        return jsonify({"error": "Unauthorized"}), 401

    user_email = session["user_email"]
    db_session = SessionLocal()
    user = db_session.query(User).filter_by(email=user_email).first()

    movie_id = request.form.get("movie_id")
    rating = request.form.get("rating")

    if not movie_id or not rating:
        return jsonify({"error": "Missing data"}), 400

    # Check if review exists
    existing = db_session.query(Review).filter_by(user_id=user.id, movie_id=movie_id).first()
    if existing:
        existing.rating = float(rating)
        existing.timestamp = datetime.utcnow()
    else:
        new_review = Review(user_id=user.id, movie_id=int(movie_id), rating=float(rating))
        db_session.add(new_review)

    db_session.commit()
    db_session.close()
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(debug=True)
