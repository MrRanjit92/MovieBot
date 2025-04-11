import pandas as pd
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["movielens"]

# File paths (adjust if needed)
movies_path = "movies.csv"
ratings_path = "ratings.csv"
tags_path = "tags.csv"
links_path = "links.csv"

# Load and insert movies
def import_movies():
    df = pd.read_csv(movies_path)
    db.movies.delete_many({})
    db.movies.insert_many(df.to_dict("records"))
    print(f"✅ Imported {len(df)} movies")

# Load and insert ratings
def import_ratings():
    df = pd.read_csv(ratings_path)
    db.ratings.delete_many({})
    db.ratings.insert_many(df.to_dict("records"))
    print(f"✅ Imported {len(df)} ratings")

# Load and insert tags
def import_tags():
    df = pd.read_csv(tags_path)
    db.tags.delete_many({})
    db.tags.insert_many(df.to_dict("records"))
    print(f"✅ Imported {len(df)} tags")

# Load and insert links
def import_links():
    df = pd.read_csv(links_path)
    db.links.delete_many({})
    db.links.insert_many(df.to_dict("records"))
    print(f"✅ Imported {len(df)} links")

if __name__ == "__main__":
    import_movies()
    import_ratings()
    import_tags()
    import_links()
    print("🎉 All CSVs imported successfully into MongoDB.")
