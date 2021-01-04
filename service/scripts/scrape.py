from bs4 import BeautifulSoup, element
import requests
import argparse

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
    return sorted(
        [
            (x.get_text().replace("'s picks", "").lower(), x.a.attrs.get("href"))
            for x in entry_list
        ]
    )


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
    return all_teams


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
    roster_slots = soup.find_all("li", class_="roster-slot")
    return roster_slots


def parse_roster_slot(slot: element.Tag) -> MutableMapping[str, Optional[str]]:
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


def parse_roster(team: Tuple) -> List[MutableMapping[str, Optional[str]]]:
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


def remap_weeks(df: pd.DataFrame) -> None:
    df["week"].replace(to_replace=constants.WEEK_REMAPPING, inplace=True)


def format_df(df: pd.DataFrame) -> None:
    df["score"] = df["score"].apply(int)
    df["user_score"] = df.groupby("user").score.transform(sum)


def format_df_after_last_week(df: pd.DataFrame) -> None:
    df["week_score"] = df.groupby(["user", "week"]).score.transform(sum)
    df["img_url"] = df["player_img"].apply(lambda x: f"{constants.BASE_URL}{x}")
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


def scrape_group(group_id: str):
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
