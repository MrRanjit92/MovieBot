from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from functools import wraps
import pickle
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import io
import csv
import requests
import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

client = MongoClient("mongodb://localhost:27017/")



SECRET_KEY = os.environ.get("SECRET_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY")


tags_df = pd.read_csv("tags.csv")  # path to tags.csv

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")

def get_tmdb_info(title=None, tmdb_id=None):
    if tmdb_id and not pd.isna(tmdb_id):
        url = f"https://api.themoviedb.org/3/movie/{int(tmdb_id)}?api_key={TMDB_API_KEY}"
    elif title:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={title}"
    else:
        return {"poster_url": None, "overview": ""}

    res = requests.get(url)
    if res.ok:
        data = res.json()
        if "results" in data and data["results"]:  # if search endpoint
            data = data["results"][0]
        return {
            "poster_url": f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get("poster_path") else None,
            "overview": data.get("overview", "")
        }

    return {"poster_url": None, "overview": ""}



app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = SECRET_KEY


# MongoDB setup
client = MongoClient(MONGO_URI)
db = client['movielens']
users_col = db['users']
ratings_col = db['ratings']
movies_col = db['movies']
chats_col = db['chats']

# Load recommendation model
with open("recommendation_model.pkl", "rb") as f:
    model = pickle.load(f)

# Load movie metadata
links_df = pd.read_csv("links.csv")
movies_df = pd.read_csv("movies.csv")

# Debug print to verify headers
print("Links columns:", links_df.columns)
print("Movies columns:", movies_df.columns)

# Check for 'movieId' before merging
if 'movieId' in links_df.columns and 'movieId' in movies_df.columns:
    movies_df = pd.merge(movies_df, links_df[['movieId', 'tmdbId']], on='movieId', how='left')
else:
    raise ValueError("Missing 'movieId' in one of the CSV files")


# Token authentication
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('x-access-token')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = users_col.find_one({'email': data['email']})
        except:
            return jsonify({'message': 'Invalid token!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Web Pages
@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/signup-page')
def signup_page():
    return render_template('signup.html')

@app.route('/chat')
def chatbot_page():
    return render_template('chatbot.html')

@app.route('/admin-dashboard')
def admin_page():
    return render_template('admin.html')

# Admin API
@app.route('/admin', methods=['GET'])
@token_required
def admin_data(current_user):
    if current_user.get("role") != "admin":
        return jsonify({"message": "Access denied"}), 403

    total_users = users_col.count_documents({})
    total_ratings = ratings_col.count_documents({})
    total_chats = chats_col.count_documents({})

    top_users = list(ratings_col.aggregate([
        {"$group": {"_id": "$userId", "rating_count": {"$sum": 1}}},
        {"$sort": {"rating_count": -1}},
        {"$limit": 5}
    ]))

    user_lookup = {}
    for u in users_col.find({}, {"userId": 1, "email": 1, "name": 1}):
        user_lookup[int(u["userId"])] = u.get("name") or u["email"]

    for user in top_users:
        user['email'] = user_lookup.get(int(user['_id']), "Unknown")

    # Chat activity
    last_7_days = datetime.utcnow() - timedelta(days=7)
    chat_logs = list(chats_col.find({"timestamp": {"$gte": last_7_days}}, {"timestamp": 1}))
    chat_day_counts = Counter(chat["timestamp"].strftime("%a") for chat in chat_logs)
    chat_chart_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    chat_chart_data = [chat_day_counts.get(day, 0) for day in chat_chart_labels]

    # Rating distribution
    rating_bins = [0, 50, 100, 500, 1000]
    bin_labels = ["<50", "50–100", "100–500", "500–1000", "1000+"]
    movie_rating_counts = list(ratings_col.aggregate([
        {"$group": {"_id": "$movieId", "count": {"$sum": 1}}}
    ]))
    counts = [m["count"] for m in movie_rating_counts]
    bin_data = [0] * len(bin_labels)
    for c in counts:
        if c < 50:
            bin_data[0] += 1
        elif c < 100:
            bin_data[1] += 1
        elif c < 500:
            bin_data[2] += 1
        elif c < 1000:
            bin_data[3] += 1
        else:
            bin_data[4] += 1

    # Genre analytics
    genre_counts = defaultdict(int)
    rating_lookup = {r["_id"]: r["count"] for r in ratings_col.aggregate([
        {"$group": {"_id": "$movieId", "count": {"$sum": 1}}}
    ])}
    for movie in movies_df.to_dict("records"):
        mid = movie["movieId"]
        if mid in rating_lookup:
            for genre in movie["genres"].split("|"):
                genre_counts[genre] += rating_lookup[mid]
    top_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return jsonify({
        "total_users": total_users,
        "total_ratings": total_ratings,
        "total_chats": total_chats,
        "top_users": top_users,
        "chart_chat_labels": chat_chart_labels,
        "chart_chat_data": chat_chart_data,
        "chart_rating_labels": bin_labels,
        "chart_rating_data": bin_data,
        "top_genres": [{"genre": g, "count": c} for g, c in top_genres]
    })

# CSV export for users
@app.route('/admin/export-users', methods=['GET'])
def export_users():
    token = request.args.get('token')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 401
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        current_user = users_col.find_one({'email': data['email']})
        if current_user.get("role") != "admin":
            return jsonify({"message": "Access denied"}), 403
    except:
        return jsonify({'message': 'Invalid token!'}), 401

    users = list(users_col.find({}, {'_id': 0, 'userId': 1, 'name': 1, 'email': 1, 'role': 1}))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['userId', 'name', 'email', 'role'])
    writer.writeheader()
    writer.writerows(users)
    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=user_data.csv'}
    )

# Signup
@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    if users_col.find_one({'email': data['email']}):
        return jsonify({'message': 'User already exists'}), 400
    last_user = users_col.find_one(sort=[("userId", -1)])
    next_user_id = last_user["userId"] + 1 if last_user else 1
    hashed_pw = generate_password_hash(data['password'])
    users_col.insert_one({
        'userId': next_user_id,
        'name': data['name'],
        'email': data['email'],
        'password_hash': hashed_pw,
        'role': data.get('role', 'user')
    })
    return jsonify({'message': 'User created successfully'}), 201

# Login
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = users_col.find_one({'email': data['email']})
    if not user or not check_password_hash(user['password_hash'], data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    token = jwt.encode({
        'email': user['email'],
        'exp': datetime.utcnow() + timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm="HS256")
    return jsonify({
        'token': token,
        'userId': user['userId'],
        'role': user.get('role', 'user')
    })
#tmdb/recommend
@app.route('/recommend', methods=['POST'])
@token_required
def recommend(current_user):
    user_id = current_user.get("userId")
    user_input = request.json.get("prompt", "").lower().strip()

    # Log user input
    chats_col.insert_one({
        "userId": user_id,
        "sender": "user",
        "message": user_input,
        "timestamp": datetime.utcnow()
    })

    # ------------------------------
    # STEP 1: Detect matching tags
    # ------------------------------
    tag_matches = tags_df[tags_df["tag"].str.lower().str.contains(user_input)]
    tagged_movie_ids = set(tag_matches["movieId"].unique())

    # ------------------------------
    # STEP 2: Genre fallback detection
    # ------------------------------
    genre_keywords = {
        "romance": ["romance", "love", "date"],
        "action": ["action", "fight", "war"],
        "comedy": ["comedy", "funny", "laugh"],
        "drama": ["drama", "serious", "emotional"],
        "sci-fi": ["sci-fi", "space", "alien"],
        "horror": ["horror", "scary", "ghost"],
        "animation": ["animation", "cartoon", "pixar"],
    }
    reference_map = {
        "titanic": "romance", "avengers": "action", "joker": "drama"
    }

    detected_genres = []

    for genre, words in genre_keywords.items():
        if any(word in user_input for word in words):
            detected_genres.append(genre)

    for movie, genre in reference_map.items():
        if movie in user_input:
            detected_genres.append(genre)

    # ------------------------------
    # STEP 3: Combine filters
    # ------------------------------
    filtered_df = movies_df

    if tagged_movie_ids:
        filtered_df = filtered_df[filtered_df["movieId"].isin(tagged_movie_ids)]
    elif detected_genres:
        pattern = "|".join(set(detected_genres))
        filtered_df = filtered_df[filtered_df["genres"].str.lower().str.contains(pattern)]

    # ------------------------------
    # STEP 4: Remove seen movies
    # ------------------------------
    rated_movie_ids = set(r['movieId'] for r in ratings_col.find({"userId": int(user_id)}))
    unseen_ids = list(set(filtered_df["movieId"].unique()) - rated_movie_ids)

    # ------------------------------
    # STEP 5: Predict and Rank
    # ------------------------------
    predictions = []
    for movie_id in unseen_ids:
        try:
            pred = model.predict(uid=int(user_id), iid=int(movie_id))
            predictions.append((movie_id, pred.est))
        except:
            continue

    top_n = sorted(predictions, key=lambda x: x[1], reverse=True)[:5]

    # ------------------------------
    # STEP 6: Format recommendations
    # ------------------------------
    recommendations = []
    for movie_id, est_rating in top_n:
        movie = movies_df[movies_df["movieId"] == movie_id].iloc[0]
        tmdb = get_tmdb_info(title=movie["title"], tmdb_id=movie.get("tmdbId"))
        recommendations.append({
            "title": movie["title"],
            "genres": movie["genres"],
            "predicted_rating": round(est_rating, 2),
            "poster_url": tmdb["poster_url"],
            "overview": tmdb["overview"]
        })

    # ------------------------------
    # STEP 7: Fallback if empty
    # ------------------------------
    if not recommendations:
        fallback_movies = movies_df.sample(5)
        for _, movie in fallback_movies.iterrows():
            tmdb = get_tmdb_info(title=movie["title"], tmdb_id=movie.get("tmdbId"))
            recommendations.append({
                "title": movie["title"],
                "genres": movie["genres"],
                "predicted_rating": "N/A",
                "poster_url": tmdb["poster_url"],
                "overview": tmdb["overview"]
            })

    # Log bot reply
    chats_col.insert_one({
        "userId": user_id,
        "sender": "bot",
        "message": f"Recommended {len(recommendations)} movies",
        "timestamp": datetime.utcnow()
    })

    return jsonify({"recommendations": recommendations})


# Get all users (Admin only)
@app.route('/admin/all-users', methods=['GET'])
@token_required
def get_all_users(current_user):
    if current_user.get("role") != "admin":
        return jsonify({"message": "Access denied"}), 403

    users = list(users_col.find({}, {'_id': 0, 'userId': 1, 'name': 1, 'email': 1, 'role': 1}))
    return jsonify(users)

# Delete user by ID (Admin only)
@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, user_id):
    if current_user.get("role") != "admin":
        return jsonify({"message": "Access denied"}), 403

    result = users_col.delete_one({'userId': user_id})
    if result.deleted_count == 1:
        return jsonify({'message': f'User {user_id} deleted'}), 200
    else:
        return jsonify({'message': 'User not found'}), 404

# Chat History
@app.route('/chat-history', methods=['GET'])
@token_required
def chat_history(current_user):
    user_id = current_user.get("userId")
    chats = list(chats_col.find({"userId": user_id}, {"_id": 0}).sort("timestamp", -1).limit(20))
    return jsonify({"chats": chats})


if __name__ == '__main__':
    app.run(debug=True)


