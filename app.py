from flask import Flask, request, jsonify
from scrape import pagify_scrape_group, parse_roster
import multiprocessing

import pandas as pd

app = Flask(__name__)


@app.route('/group_get/', methods=['GET'])
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

    if len(all_teams)==0:
        response["ERROR"] = "No teams found for that group"
        return jsonify(response)
    # create sorted list of users and their urls
    team_names = [x.a.text.replace("'s picks", "").lower() for x in all_teams]
    team_links = [x.a.attrs['href'] for x in all_teams]
    teams_sorted = sorted(list(zip(team_names, team_links)))

    # create list of all rosters
    all_rosters = []

    with multiprocessing.Pool() as p:
        all_rosters = p.map(parse_roster, teams_sorted)

    # conver to pandas and save to csv
    flat_all_rosters = [item for sublist in all_rosters for item in sublist]
    df_all_rosters = pd.DataFrame(flat_all_rosters)

    group_by_columns = ['user', 'week']
    remaining_columns = list(set(df_all_rosters.columns) -
                             set(group_by_columns))

    j = (df_all_rosters.groupby(group_by_columns)
         .apply(lambda x: x[remaining_columns].to_dict(orient='records')))

    j_user = j.unstack('user').to_dict()
    j_week = j.unstack('week').to_dict()
    response['response'] = {'user': j_user, 'week': j_week}

    # Return the response in json format
    return jsonify(response)


# A welcome message to test our server
@app.route('/')
def index():
    return "<h1>Welcome to our server !!</h1>"

if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    app.run(threaded=True, port=5000)