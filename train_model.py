import pandas as pd
from surprise import Dataset, Reader, SVD
from surprise.model_selection import train_test_split
import pickle
from pymongo import MongoClient

# Load ratings from MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["movielens"]
ratings_data = list(db.ratings.find({}, {"_id": 0}))

# Convert to DataFrame
ratings_df = pd.DataFrame(ratings_data)

# Surprise reader
reader = Reader(rating_scale=(0.5, 5.0))
data = Dataset.load_from_df(ratings_df[['userId', 'movieId', 'rating']], reader)

# Train/test split and model
trainset, testset = train_test_split(data, test_size=0.2, random_state=42)
model = SVD()
model.fit(trainset)

# Save model to a file
with open("recommendation_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("✅ Model trained and saved as recommendation_model.pkl")
