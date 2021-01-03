from bs4 import BeautifulSoup
import requests
import argparse

import pandas as pd
import multiprocessing

from scripts import constants


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
    entry_list = soup.find_all("td", class_="groupEntryName")
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
        url = f"{constants.BASE_URL}/group/{group_id}?offset={offset}"
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
    url_prefix = constants.BASE_URL
    url = url_prefix + url_suffix
    page = requests.get(url)
    soup = BeautifulSoup(page.content, features="lxml")
    roster_slots = soup.find_all("li", class_="roster-slot")
    return roster_slots


def parse_roster_slot(slot):
    slot_attrs = slot.div.attrs
    slot_id = slot_attrs.get("id")
    if not slot_id:
        return {}

    player_first_name = (
        slot.find("span", class_="first-name").text
        if slot.find("span", class_="first-name")
        else ""
    )

    player_last_name = (
        slot.find("span", class_="last-name").text
        if slot.find("span", class_="first-name")
        else ""
    )

    score = (
        slot.find("span", class_="display pts player-pts").em.text
        if slot.find("span", class_="display pts player-pts")
        else "0"
    )

    team_id = slot_attrs.get("data-sport-team-id")
    return {
        "player_name": " ".join([player_first_name, player_last_name]),
        "position": slot_attrs.get("data-player-position"),
        "week": slot_id.rsplit("-", 2)[-2],
        "roster_slot": slot_id.rsplit("-", 1)[-1],
        "multiplier": slot_attrs.get("data-player-multiplier"),
        "team": team_id,
        "score": score,
        "player_img": slot.find("img", class_="player-img").attrs.get("src"),
    }


def parse_roster(team):
    user, url_suffix = team
    roster = scrape_team(url_suffix)
    roster_parsed = []
    for slot in roster:
        slot_dict = parse_roster_slot(slot)
        if not slot_dict:
            continue
        slot_dict.update({"user": user})
        roster_parsed.append(slot_dict)
    return roster_parsed


def remap_weeks(df):
    df["week"].replace(to_replace=constants.WEEK_REMAPPING, inplace=True)


def format_df(df):
    df["score"] = df["score"].apply(int)
    df["user_score"] = df.groupby("user").score.transform(sum)


def format_df_after_last_week(df):
    df["week_score"] = df.groupby(["user", "week"]).score.transform(sum)
    df["img_url"] = df["player_img"].apply(lambda x: f"{constants.BASE_URL}{x}")
    df.drop(columns=["player_img"], inplace=True)
    df["team"] = df["team"].apply(lambda x: constants.TEAM_DICTIONARY.get(x, x))
    df = df.astype(str)


def create_total_week_df(df):
    exclude_future_unrevealed = df[
        ((df.player_name != " ") | (df.week == df.week.min()))
    ]
    grouped_by_position = exclude_future_unrevealed.groupby(["user", "roster_slot"])
    roster_scores = grouped_by_position.score.apply(sum).to_dict()
    last_slots = grouped_by_position.tail(1)
    last_slots["week"] = "total"
    last_slots["score"] = last_slots.apply(
        lambda r: roster_scores[(r.user, r.roster_slot)], axis=1
    )
    return last_slots


def df_to_json(df):
    remap_weeks(df)
    format_df(df)
    total_slots_df = create_total_week_df(df)
    df = pd.concat([df, total_slots_df])
    format_df_after_last_week(df)
    group_by_user_dict = {
        week: sorted(
            [
                {
                    "user": user,
                    "roster": df_user.to_dict(orient="records"),
                    "week_score": str(df_user.score.sum()),
                }
                for user, df_user in df_week.groupby("user")
            ],
            key=lambda x: int(x["week_score"]),
            reverse=True,
        )
        for week, df_week in df.groupby("week")
    }
    return {"users": group_by_user_dict}


def convert_group_teams_to_df(all_teams):

    # create sorted list of users and their urls
    team_names = [x.a.text.replace("'s picks", "").lower() for x in all_teams]
    team_links = [x.a.attrs["href"] for x in all_teams]
    teams_sorted = sorted(list(zip(team_names, team_links)))

    # create list of all rosters
    with multiprocessing.Pool() as p:
        all_rosters = p.map(parse_roster, teams_sorted)

    # convert to pandas and save to df
    flat_all_rosters = [item for sublist in all_rosters for item in sublist]
    df_all_rosters = pd.DataFrame(flat_all_rosters)
    return df_all_rosters


def remove_non_participants(all_teams, remove_list):
    return [x for x in all_teams if x.text not in remove_list]


def scrape_group(group_id):
    response = {}
    if not group_id:
        response["ERROR"] = "no group found, please send a group."
        return response

    # scrape group pages
    all_teams = pagify_scrape_group(group_id)
    if len(all_teams) == 0:
        response["ERROR"] = "No teams found for that group"
        return response

    filtered_teams = remove_non_participants(all_teams, constants.REMOVE_LIST)
    df_all_rosters = convert_group_teams_to_df(filtered_teams)
    json_rosters = df_to_json(df_all_rosters)
    response["response"] = json_rosters
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group")
    args = parser.parse_args()
    scrape_group(args.group)


if __name__ == "__main__":
    main()
