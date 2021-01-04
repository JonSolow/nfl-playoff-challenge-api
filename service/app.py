from flask import Flask, request, jsonify
from flask_caching import Cache
from flask_cors import CORS, cross_origin
from scripts.scrape import scrape_group
import os


config = {
    "DEBUG": True,  # some Flask specific configs
    "CACHE_TYPE": "simple",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300,
}

app = Flask(__name__)
port = int(os.getenv("PORT", "5000"))
cors = CORS(app, resources={r"/api/": {"origins": r"*"}})

app.config.from_mapping(config)
cache = Cache(app)


@cache.memoize(timeout=120)
def cached_scrape_group(group_id):
    print(f"external call for : {group_id}")
    return jsonify(scrape_group(group_id))


@app.route("/api/", methods=["GET"])
@cross_origin()
def respond():
    # Retrieve the name from url parameter
    group_id = request.args.get("group", None)

    # For debugging
    print(f"got group_id: {group_id}")

    return cached_scrape_group(group_id)


# A welcome message to test our server
@app.route("/")
def index():
    return "<h1>Welcome to our server !!</h1>"


if __name__ == "__main__":
    # Threaded option to enable multiple instances
    # for multiple user access support
    app.run(threaded=True, host="0.0.0.0", port=port)
