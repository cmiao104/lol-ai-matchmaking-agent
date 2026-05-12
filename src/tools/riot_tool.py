from typing import Dict, Any
from services.riot_api import (
    get_last_match_by_riot_id,
    get_recent_matches_by_riot_id,
)

PLATFORM_TO_REGION = {
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "euw1": "europe",
    "eun1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "kr": "asia",
    "jp1": "asia",
    "oc1": "sea",
    "ph2": "sea",
    "sg2": "sea",
    "th2": "sea",
    "tw2": "sea",
    "vn2": "sea",
}


def normalize_region(region: str) -> str:
    region = (region or "americas").lower().strip()
    return PLATFORM_TO_REGION.get(region, region)


def _summarize_match(match: Dict[str, Any]) -> Dict[str, Any]:
    kills = match.get("kills", 0)
    deaths = match.get("deaths", 0)
    assists = match.get("assists", 0)

    kda_value = round((kills + assists) / max(1, deaths), 2)

    return {
        "match_id": match.get("match_id"),
        "game_mode": match.get("game_mode"),
        "queue_id": match.get("queue_id"),
        "queue_name": match.get("queue_name"),
        "champion": match.get("champion"),
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda_text": match.get("kda_text"),
        "kda_value": kda_value,
        "win": match.get("win"),
        "cs": match.get("cs"),
        "champ_level": match.get("champ_level") or match.get("champion_level"),
        "gold_earned": match.get("gold_earned"),
        "damage_to_champions": match.get("damage_to_champions"),
        "vision_score": match.get("vision_score"),
        "wards_placed": match.get("wards_placed"),
        "wards_killed": match.get("wards_killed"),
        "game_duration_minutes": match.get("game_duration_minutes"),
    }


def get_last_match_summary(
    game_name: str,
    tag_line: str,
    region: str = "americas",
) -> Dict[str, Any]:
    try:
        region = normalize_region(region)

        match = get_last_match_by_riot_id(game_name, tag_line, region)

        return {
            "success": True,
            "game_name": game_name,
            "tag_line": tag_line,
            "region": region,
            "match": _summarize_match(match),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def get_recent_match_summaries(
    game_name: str,
    tag_line: str,
    region: str = "americas",
    count: int = 10,
) -> Dict[str, Any]:
    try:
        region = normalize_region(region)
        count = max(1, min(int(count), 10))

        matches = get_recent_matches_by_riot_id(
            game_name=game_name,
            tag_line=tag_line,
            region=region,
            count=count,
        )

        summaries = [_summarize_match(m) for m in matches]

        wins = sum(1 for m in summaries if m.get("win"))
        losses = len(summaries) - wins

        return {
            "success": True,
            "game_name": game_name,
            "tag_line": tag_line,
            "region": region,
            "count": len(summaries),
            "wins": wins,
            "losses": losses,
            "winrate": round(wins / max(1, len(summaries)), 3),
            "avg_kda": round(
                sum(m.get("kda_value", 0) for m in summaries) / max(1, len(summaries)),
                2
            ),
            "avg_deaths": round(
                sum(m.get("deaths", 0) for m in summaries) / max(1, len(summaries)),
                2
            ),
            "avg_damage_to_champions": round(
                sum(m.get("damage_to_champions", 0) or 0 for m in summaries) / max(1, len(summaries)),
                2
            ),
            "avg_vision_score": round(
                sum(m.get("vision_score", 0) or 0 for m in summaries) / max(1, len(summaries)),
                2
            ),
            "matches": summaries,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }