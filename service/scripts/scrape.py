from bs4 import BeautifulSoup, element
import requests
import argparse

import json
import time
import pandas as pd
import multiprocessing

from scripts import constants

from typing import List, Optional, Tuple, MutableMapping, Any


def scrape_teams_group_page(url: str) -> List[Tuple[str, str]]:
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
    entry_tuples = group_page_to_name_link_tuples(entry_list)
    return entry_tuples


def group_page_to_name_link_tuples(
    entry_list: element.ResultSet,
) -> List[Tuple[str, str]]:
    return [
        (x.get_text().replace("'s picks", "").lower(), x.a.attrs.get("href"))
        for x in entry_list
    ]


def pagify_scrape_group(group_id: str) -> List[Tuple[str, str]]:
    """Pagify through each page of a group until all teams are added

    Arguments:
        group_id {str} -- Last 5 digits of group url
    """
    # pagify scrape until empty list returned
    all_teams = []
    empty: bool = False
    offset: int = 0
    while not empty:
        url: str = f"{constants.BASE_URL}/group/{group_id}?offset={offset}"
        page_team_tuples = scrape_teams_group_page(url)
        if len(page_team_tuples) == 0:
            empty = True
        # each page can have 16 teams
        offset += 16
        all_teams.extend(page_team_tuples)
    return sorted(all_teams, key=lambda x: x[0])


def scrape_team(url_suffix: str) -> element.ResultSet:
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
    roster_slots = soup.find_all("div", class_="player")
    parsed_roster_slots = [parse_roster_slot(s) for s in roster_slots]
    return parsed_roster_slots


def replace_if_none(
    value: Any, default_replace: Optional[Any] = None, lambda_fxn=lambda x: x
):
    return lambda_fxn(value) if value else default_replace


def player_dict_from_slot_id(slot: element.Tag) -> MutableMapping[str, Optional[str]]:
    slot_id = slot.get("id", "--")
    _, week, roster_slot = slot_id.rsplit("-", 2)
    data_player_id = slot.get("data-player-id", "")
    return {
        "week": week,
        "roster_slot": roster_slot,
        "data-player-id": data_player_id,
    }


def player_dict_from_slot_attrs(
    slot: element.Tag,
) -> MutableMapping[str, Optional[str]]:
    team_id = slot.get("data-sport-team-id")
    position = slot.get("data-player-position")
    multiplier = slot.get("data-player-multiplier")
    return {
        "position": position,
        "multiplier": multiplier,
        "team": team_id,
    }


def player_dict_from_finds(slot: element.Tag) -> MutableMapping[str, Optional[str]]:
    player_first_name = replace_if_none(
        slot.find("span", class_="first-name"), "", lambda x: x.text
    )
    player_last_name = replace_if_none(
        slot.find("span", class_="last-name"), "", lambda x: x.text
    )

    player_name = " ".join([player_first_name, player_last_name])
    score = replace_if_none(
        slot.find("span", class_="display pts player-pts"), "0", lambda x: x.em.text
    )
    player_img = slot.find("img", class_="player-img").attrs.get("src")
    return {
        "player_name": player_name,
        "score": score,
        "player_img": player_img,
    }


def parse_roster_slot(slot: element.Tag) -> MutableMapping[str, Optional[str]]:
    player_dict = player_dict_from_slot_id(slot)
    player_dict.update(player_dict_from_slot_attrs(slot))
    player_dict.update(player_dict_from_finds(slot))
    return player_dict


def parse_roster(team: Tuple) -> List[MutableMapping[str, Optional[str]]]:
    user, url_suffix = team
    roster = scrape_team(url_suffix)
    roster_with_user = []
    for roster_slot_dict in roster:
        if not roster_slot_dict:
            continue
        roster_slot_dict.update({"user": user})
        roster_with_user.append(roster_slot_dict)
    return roster_with_user


def format_df(df: pd.DataFrame) -> None:
    df["score"] = df["score"].apply(int)
    df["user_score"] = df.groupby("user").score.transform(sum)


def format_player_img_url(player_img: str) -> str:
    # some img paths are relative and some are explicit
    if len(player_img) < 4:
        return player_img
    elif player_img[:4] == "http":
        return player_img
    else:
        return f"{constants.BASE_URL}{player_img}"


def format_df_after_last_week(df: pd.DataFrame) -> None:
    df["week_score"] = df.groupby(["user", "week"]).score.transform(sum)
    df["img_url"] = df["player_img"].apply(format_player_img_url)
    df.drop(columns=["player_img"], inplace=True)
    df["team"] = df["team"].apply(lambda x: constants.TEAM_DICTIONARY.get(x, x))
    df = df.astype(str)


def create_total_week_df(df: pd.DataFrame) -> pd.DataFrame:
    exclude_future_unrevealed = df[
        ((df.player_name != " ") | (df.week == df.week.min()))
    ]
    grouped_by_position = exclude_future_unrevealed.groupby(["user", "roster_slot"])
    roster_scores = grouped_by_position.score.apply(sum).to_dict()
    last_slots = grouped_by_position.tail(1)
    last_slots.loc[:, "week"] = "total"
    last_slots["score"] = last_slots.apply(
        lambda r: roster_scores[(r.user, r.roster_slot)], axis=1
    )
    return last_slots


def df_to_json(df):
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


def convert_group_teams_to_df(teams_sorted: List[Tuple[str, str]]):

    # create list of all rosters
    use_multiprocessing = False
    if use_multiprocessing:
        with multiprocessing.Pool() as p:
            all_rosters = p.map(parse_roster, teams_sorted)
    else:
        all_rosters = [parse_roster(t) for t in teams_sorted]

    # convert to pandas and save to df
    flat_all_rosters = [item for sublist in all_rosters for item in sublist]
    df_all_rosters = pd.DataFrame(flat_all_rosters)
    return df_all_rosters


def remove_non_participants(
    all_teams: List[Tuple[str, str]], remove_list: List
) -> List[Tuple[str, str]]:
    return [x for x in all_teams if x[0] not in remove_list]


def generate_timpestamp() -> MutableMapping[str, float]:
    current_time = time.time()
    return {"timestamp": current_time}


def remap_team_names_for_game_dict(game_dict):
    for key in ["homeTeamId", "awayTeamId"]:
        team_id = str(game_dict[key])
        game_dict[key] = constants.TEAM_DICTIONARY.get(team_id, team_id)


def parse_games_from_week(week_dict):
    parsed_games = {}
    games_dict = week_dict["nflGames"]
    if not isinstance(games_dict, dict):
        return {}
    for game in games_dict.values():
        remap_team_names_for_game_dict(game)
        parsed_games[game["homeTeamId"]] = game
        parsed_games[game["awayTeamId"]] = game
    return parsed_games


def parse_week_stats(week: str):
    url = f"{constants.BASE_URL}/players/weekstats?week={week}&season={constants.CURRENT_SEASON}"
    resp = requests.get(url)
    week_dict = json.loads(resp.content)
    player_stats_dict = {
        k: v["stats"]
        for k, v in week_dict["players"].items()
        if isinstance(v["stats"], dict)
    }
    team_games_dict = parse_games_from_week(week_dict)
    return player_stats_dict, team_games_dict


def assemble_all_week_stats() -> MutableMapping[str, MutableMapping[Any, Any]]:
    weeks = map(str, range(1, 5))
    stats_dict: MutableMapping = {}
    for week in weeks:
        stats_dict[week] = {}
        stats_dict[week]["stats"], stats_dict[week]["games"] = parse_week_stats(week)
    return stats_dict


def scrape_group(group_id: str):
    response: MutableMapping[str, Any] = {}
    response.update(generate_timpestamp())
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
    json_rosters.update({"week_stats": assemble_all_week_stats()})
    response["response"] = json_rosters
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--group")
    args = parser.parse_args()
    scrape_group(args.group)


if __name__ == "__main__":
    main()
