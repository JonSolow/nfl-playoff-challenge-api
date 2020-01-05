from bs4 import BeautifulSoup
import requests
import argparse
import time

import pandas as pd
import multiprocessing

TEAM_DICTIONARY = {None: None,
                   '21': 'NE',
                   '13': 'HOU',
                   '20': 'MIN',
                   '22': 'NO',
                   '12': 'TEN',
                   '3': 'BUF',
                   '30': 'SEA'
                   }


def scrape_teams_group_page(url):
    """Scrapes the teams from an NFL Playoff Challenge group

    Arguments:
        url {str} -- URL of the group
            (example: "https://playoffchallenge.fantasy.nfl.com/group/99999")

    Returns:
        entry_list {List} -- List of bs4 elements
                             containg each entry's team name and url
    """
    page = requests.get(url)
    soup = BeautifulSoup(page.content, features="lxml")
    entry_list = soup.find_all('td', class_='groupEntryName')
    return entry_list


def pagify_scrape_group(group_id):
    """Pagify through each page of a group until all teams are added

    Arguments:
        group_id {str} -- Last 5 digits of group url
    """
    # pagify scrape until empty list returned
    all_teams = []
    empty = False
    offset = 0
    while not empty:
        url = "https://playoffchallenge.fantasy.nfl.com/group/{}?offset={}"\
            .format(group_id, offset)
        page = scrape_teams_group_page(url)
        if len(page) == 0:
            empty = True
        # each page can have 16 teams
        offset += 16
        all_teams.extend(page)
    return all_teams


def scrape_team(url_suffix):
    """Scrapes the roster in list of bs4 elements

    Arguments:
        url_suffix {str} -- Ending of URL for one user's picks
                            (example: "/entry?entryId=9999999")

    Returns:
        roster_slots [type] -- [description]
    """
    url_prefix = 'https://playoffchallenge.fantasy.nfl.com'
    url = url_prefix + url_suffix
    page = requests.get(url)
    soup = BeautifulSoup(page.content, features="lxml")
    roster_slots = soup.find_all('li', class_='roster-slot')
    return roster_slots


def parse_roster(team):
    user, url_suffix = team
    roster = scrape_team(url_suffix)
    roster_parsed = []
    for slot in roster:
        slot_attrs = slot.div.attrs
        slot_id = slot_attrs.get('id')
        if not slot_id:
            continue

        player_first_name = slot.find('span', class_='first-name').text \
            if slot.find('span', class_='first-name') else ''

        player_last_name = slot.find('span', class_='last-name').text \
            if slot.find('span', class_='first-name') else ''

        score = slot.find('span', class_="display pts player-pts").em.text \
            if slot.find('span', class_="display pts player-pts") else 0

        team_id = slot_attrs.get('data-sport-team-id')
        # player_img = slot.find('img', class_='player-img').attrs.get('src')

        roster_parsed.append({'user': user,
                              'player_name': ' '.join(
                                  [player_first_name, player_last_name]),
                              'position': slot_attrs.get(
                                  'data-player-position'),
                              'week': slot_id.rsplit('-', 2)[-2],
                              'roster_slot': slot_id.rsplit('-', 1)[-1],
                              'multiplier': slot_attrs.get(
                                  'data-player-multiplier'),
                              'team': TEAM_DICTIONARY.get(team_id, team_id),
                              'score': score,
                              #   'player_img': player_img,
                              })
    return roster_parsed


def df_to_json(df):
    # make scores int
    df['score'] = df['score'].apply(int)
    df['week_score'] = df.groupby(['user', 'week']).score.transform(sum)
    df['user_score'] = df.groupby('user').score.transform(sum)
    df = df.astype(str)
    player_columns = ['player_name', 'position', 'roster_slot',
                      'multiplier', 'team', 'score']

    j_user = []
    for user, data_user in df.groupby(['user']):
        user_dict = {}
        user_dict['user'] = user
        user_dict['total_score'] = data_user.user_score.values[0]
        user_dict['weekly'] = {}

        for week, data_week in data_user.groupby('week'):
            user_dict['weekly'][week] = {}
            user_dict['weekly'][week]['week_score'] = data_week['week_score']\
                .values[0]
            user_dict['weekly'][week]['roster'] = data_week[player_columns]\
                .to_dict(orient='records')
            continue
        j_user.append(user_dict)
    return {'users': j_user, 'weeks': None}


def save_json(json_dict):
    j_user = json_dict['users']
    # j_week = json_dict['weeks']

    with open('rosters_by_user.json', 'w') as f:
        f.write(j_user)
        f.close()

    print('saved to json')


def convert_group_teams_to_df(all_teams):

    # create sorted list of users and their urls
    team_names = [x.a.text.replace("'s picks", "").lower() for x in all_teams]
    team_links = [x.a.attrs['href'] for x in all_teams]
    teams_sorted = sorted(list(zip(team_names, team_links)))

    # create list of all rosters
    with multiprocessing.Pool() as p:
        all_rosters = p.map(parse_roster, teams_sorted)

    # convert to pandas and save to csv
    flat_all_rosters = [item for sublist in all_rosters for item in sublist]
    df_all_rosters = pd.DataFrame(flat_all_rosters)
    return df_all_rosters


def main():
    start = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument('--group')
    args = parser.parse_args()

    all_teams = pagify_scrape_group(args.group)
    df_all_rosters = convert_group_teams_to_df(all_teams)
    df_all_rosters.to_csv('rosters.csv')

    json_rosters = df_to_json(df_all_rosters)
    # save_json(json_rosters)

    end = time.time()
    print("total time: ", end - start)


if __name__ == '__main__':
    main()
