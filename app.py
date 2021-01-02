from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from scripts.scrape import scrape_group

import os
import tracemalloc
import psutil

app = Flask(__name__)
cors = CORS(app, resources={r"/api/": {"origins": r"*"}})
process = psutil.Process(os.getpid())
tracemalloc.start()
s = None

@app.route('/memory')
def print_memory():
    return {'memory': process.memory_info().rss}


@app.route("/snapshot")
def snap():
    global s
    if not s:
        s = tracemalloc.take_snapshot()
        return "taken snapshot\n"
    else:
        lines = []
        top_stats = tracemalloc.take_snapshot().compare_to(s, 'lineno')
        for stat in top_stats[:5]:
            lines.append(str(stat))
        return "\n".join(lines)


@app.route('/api/', methods=['GET'])
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
    app.run(threaded=True, port=5000)
