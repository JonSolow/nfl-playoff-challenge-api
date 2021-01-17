from typing import List, Mapping

# Team ID codes to short names
TEAM_DICTIONARY: Mapping[str, str] = {
    "2": "BAL",
    "3": "BUF",
    "5": "CHI",
    "7": "CLE",
    "11": "GB",
    "12": "TEN",
    "13": "HOU",
    "14": "IND",
    "16": "KC",
    "17": "LAR",
    "20": "MIN",
    "21": "NE",
    "22": "NO",
    "27": "PIT",
    "29": "SF",
    "30": "SEA",
    "31": "TB",
    "32": "WSH",
}

BASE_URL: str = "https://playoffchallenge.fantasy.nfl.com"

# teams to remove
REMOVE_LIST: List[str] = []


CURRENT_SEASON: str = "2020"

STAT_KEY_MAP: Mapping[str, str] = {
    "5": "PYd",
    "6": "PTD",
    "7": "INT",
    "14": "RuYd",
    "15": "RuTD",
    "21": "ReYd",
    "22": "ReTD",
    "30": "Fum",
    "45": "Sack",
    "46": "DefINT",
    "47": "DefFum",
    "50": "DefTD",
    "54": "PtsAllow",
}
