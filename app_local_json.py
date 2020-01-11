from flask import Flask, jsonify
from flask_cors import CORS, cross_origin
import json

app = Flask(__name__)
cors = CORS(app, resources={r"/api/": {"origins": r"*"}})


@app.route('/api/', methods=['GET'])
@cross_origin()
def respond():

    json_rosters = json.load(open('rosters_by_user.json', 'r'))

    response = json_rosters

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
