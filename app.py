# app.py
import os
import requests
import openai
import schedule
import time
from flask import Flask, render_template, abort
from datetime import datetime
from bs4 import BeautifulSoup
import hashlib
from dotenv import load_dotenv

# --- LOAD ENV VARS ---
load_dotenv()

# --- CONFIG ---
NEWS_API_KEY = os.getenv("NEWSDATA_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

CATEGORIES = ["world", "technology", "economics"]
NEWS_API_URL = "https://newsdata.io/api/1/news"

# Create folder for articles if it doesn't exist
os.makedirs("articles", exist_ok=True)

app = Flask(__name__)

# --- FETCH AND REWRITE FUNCTION ---
def fetch_and_rewrite_articles():
    for category in CATEGORIES:
        print(f"Fetching category: {category}")
        params = {
            "apikey": NEWS_API_KEY,
            "category": category,
            "language": "en",
            "country": "us"
        }
        res = requests.get(NEWS_API_URL, params=params)
        if res.status_code != 200:
            print(f"Failed to fetch news: {res.text}")
            continue

        news_data = res.json().get("results", [])
        for article in news_data[:3]:  # Limit to top 3 per category to reduce cost
            if not article.get("title"):
                continue

            # Rewriting article
            prompt = f"Rewrite the following news article professionally, like a journalist would, for SEO and clarity. Keep it under 800 words.\n\nTitle: {article['title']}\n\nContent: {article.get('content') or article.get('description') or ''}"
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                rewritten = response["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"OpenAI error: {e}")
                continue

            # Clean title for filename
            article_id = hashlib.md5(article['title'].encode()).hexdigest()
            filename = f"articles/{article_id}.html"

            # Prevent copyrighted images
            image_url = article.get("image_url") or ""
            if any(x in image_url for x in ["getty", "reuters", "apnews", "cnn"]):
                image_url = None

            article_html = render_template("article_template.html",
                title=article["title"],
                content=rewritten,
                category=category,
                image=image_url,
                pub_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                source=article.get("source_id", "Unknown")
            )
            with open(filename, "w", encoding="utf-8") as f:
                f.write(article_html)

# --- SCHEDULER ---
schedule.every(1).hours.do(fetch_and_rewrite_articles)

# --- ROUTES ---
@app.route("/")
def homepage():
    articles = []
    for file in os.listdir("articles"):
        with open(os.path.join("articles", file), encoding="utf-8") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
            title = soup.find("h1").text
            category = soup.find("meta", {"name": "category"})["content"]
            articles.append({"title": title, "file": file, "category": category})
    return render_template("index.html", articles=articles)

@app.route("/article/<article_id>")
def show_article(article_id):
    filepath = f"articles/{article_id}.html"
    if not os.path.exists(filepath):
        abort(404)
    with open(filepath, encoding="utf-8") as f:
        return f.read()

# --- RUN SCHEDULER IN BACKGROUND ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == '__main__':
    fetch_and_rewrite_articles()  # Trigger once for testing
    import threading
    threading.Thread(target=run_scheduler).start()
    app.run(debug=True)
