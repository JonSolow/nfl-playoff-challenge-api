from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from scripts.scrape import scrape_group


app = Flask(__name__)
cors = CORS(app, resources={r"/api/": {"origins": r"*"}})


@app.route('/api/', methods=['GET'])
@cross_origin()
def respond():
    # Retrieve the name from url parameter
    group_id = request.args.get("group", None)
    use_sample_roster = request.args.get("sample", False)

    # For debugging
    print(f"got group_id: {group_id}")

    response = scrape_group(group_id, use_sample_roster=use_sample_roster)

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
