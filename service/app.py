from flask import Flask, request, jsonify
from flask_caching import Cache
from flask_cors import CORS, cross_origin
from scripts.scrape import scrape_group
import os


config = {
    "DEBUG": True,          # some Flask specific configs
    "CACHE_TYPE": "simple", # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__)
port = int(os.getenv("PORT", "5000"))
cors = CORS(app, resources={r"/api/": {"origins": r"*"}})

app.config.from_mapping(config)
cache = Cache(app)

@app.route('/api/', methods=['GET'])
@cache.memoize(timeout=120)
@cross_origin()
def respond():
    # Retrieve the name from url parameter
    group_id = request.args.get("group", None)

    # For debugging
    print(f"got group_id: {group_id}")

    response = scrape_group(group_id)

    # Return the response in json format
    return jsonify(response)


# A welcome message to test our server
@app.route('/')
def index():
    return "<h1>Welcome to our server !!</h1>"


if __name__ == '__main__':
    # Threaded option to enable multiple instances
    # for multiple user access support
    app.run(threaded=True, host="0.0.0.0", port=port)
