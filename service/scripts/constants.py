from typing import List, Mapping

# Team ID codes to short names
TEAM_DICTIONARY: Mapping[str, str] = {
    "2": "BAL",
    "3": "BUF",
    "7": "CLE",
    "11": "GB",
    "12": "TEN",
    "13": "HOU",
    "16": "KC",
    "20": "MIN",
    "21": "NE",
    "22": "NO",
    "27": "PIT",
    "29": "SF",
    "30": "SEA",
    "31": "TB",
}

BASE_URL: str = "https://playoffchallenge.fantasy.nfl.com"

# teams to remove
REMOVE_LIST: List[str] = []


WEEK_REMAPPING: Mapping[str, str] = {
    "1": "18",
    "2": "19",
    "3": "20",
    "4": "22",
}
