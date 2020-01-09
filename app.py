from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from scrape import pagify_scrape_group
from scrape import df_to_json, convert_group_teams_to_df


app = Flask(__name__)
# cors = CORS(app, resources={r"/api/": {"origins": r"https://playoffchallengefrontend.herokuapp.com/*"}})
cors = CORS(app, resources={r"/api/": {"origins": r"*"}})


@app.route('/api/', methods=['GET'])
@cross_origin
def respond():
    # Retrieve the name from url parameter
    group_id = request.args.get("group", None)

    # For debugging
    print(f"got group_id: {group_id}")

    response = {}

    # Check if user sent a name at all
    if not group_id:
        response["ERROR"] = "no group found, please send a group."
        return jsonify(response)

    all_teams = pagify_scrape_group(group_id)

    if len(all_teams) == 0:
        response["ERROR"] = "No teams found for that group"
        return jsonify(response)

    df_all_rosters = convert_group_teams_to_df(all_teams)
    json_rosters = df_to_json(df_all_rosters)

    response['response'] = json_rosters

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
