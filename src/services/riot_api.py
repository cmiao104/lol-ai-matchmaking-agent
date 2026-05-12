import os
import requests
from typing import Dict, Any, List, Optional

RIOT_API_KEY = os.getenv("RIOT_API_KEY")

if not RIOT_API_KEY:
    raise ValueError("RIOT_API_KEY was not loaded. Please check your .env file.")


QUEUE_NAME_MAP = {
    400: "Normal Draft",
    420: "Ranked Solo/Duo",
    430: "Normal Blind",
    440: "Ranked Flex",
    450: "ARAM",
    700: "Clash",
    1700: "Arena",
}


def _riot_get(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    headers = {
        "X-Riot-Token": RIOT_API_KEY
    }

    response = requests.get(url, headers=headers, params=params, timeout=15)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response.json()


def get_account_by_riot_id(game_name: str, tag_line: str, region: str) -> Dict[str, Any] | None:
    url = f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
    return _riot_get(url)


def get_match_ids_by_puuid(puuid: str, region: str, start: int = 0, count: int = 1) -> List[str]:
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    data = _riot_get(url, params={"start": start, "count": count})
    return data or []


def get_match_detail(match_id: str, region: str) -> Dict[str, Any] | None:
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return _riot_get(url)


def get_queue_name(queue_id: int) -> str:
    return QUEUE_NAME_MAP.get(queue_id, f"Queue {queue_id}")


def _find_player(match_detail: Dict[str, Any], puuid: str) -> Dict[str, Any]:
    info = match_detail.get("info", {})
    participants = info.get("participants", [])
    player = next((p for p in participants if p.get("puuid") == puuid), None)

    if not player:
        raise ValueError("Player was not found in match participants.")

    return player


def _calculate_cs(player: Dict[str, Any]) -> int:
    total_minions = player.get("totalMinionsKilled", 0)
    neutral_minions = player.get("neutralMinionsKilled", 0)
    return total_minions + neutral_minions


def _calculate_duration_minutes(info: Dict[str, Any]) -> float:
    game_duration = info.get("gameDuration", 0)
    return round(game_duration / 60, 1) if game_duration else 0


def extract_player_match_summary(match_detail: Dict[str, Any], puuid: str) -> Dict[str, Any]:
    metadata = match_detail.get("metadata", {})
    info = match_detail.get("info", {})
    player = _find_player(match_detail, puuid)

    cs = _calculate_cs(player)
    duration_min = _calculate_duration_minutes(info)

    kills = player.get("kills", 0)
    deaths = player.get("deaths", 0)
    assists = player.get("assists", 0)
    queue_id = info.get("queueId", 0)

    return {
        "match_id": metadata.get("matchId"),
        "game_mode": info.get("gameMode"),
        "queue_id": queue_id,
        "queue_name": get_queue_name(queue_id),
        "champion": player.get("championName"),
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "kda_text": f"{kills}/{deaths}/{assists}",
        "win": player.get("win"),
        "cs": cs,
        "champ_level": player.get("champLevel"),
        "gold_earned": player.get("goldEarned"),
        "damage_to_champions": player.get("totalDamageDealtToChampions"),
        "vision_score": player.get("visionScore"),
        "wards_placed": player.get("wardsPlaced"),
        "wards_killed": player.get("wardsKilled"),
        "largest_killing_spree": player.get("largestKillingSpree"),
        "double_kills": player.get("doubleKills"),
        "triple_kills": player.get("tripleKills"),
        "quadra_kills": player.get("quadraKills"),
        "penta_kills": player.get("pentaKills"),
        "champion_level": player.get("champLevel"),
        "gold_earned": player.get("goldEarned"),
        "damage_taken": player.get("totalDamageTaken"),
        "healing_done": player.get("totalHeal"),
        "time_ccing_others": player.get("timeCCingOthers"),
        "kill_participation_hint": None,  # later if you want team total kills
        "game_duration_seconds": info.get("gameDuration", 0),
        "game_duration_minutes": duration_min,
        "riot_id_game_name": player.get("riotIdGameName"),
        "riot_id_tagline": player.get("riotIdTagline"),
    }


def get_last_match_by_riot_id(game_name: str, tag_line: str, region: str) -> Dict[str, Any]:
    account = get_account_by_riot_id(game_name, tag_line, region)
    if not account:
        raise ValueError("Riot account was not found.")

    puuid = account.get("puuid")
    if not puuid:
        raise ValueError("PUUID was not found for this Riot account.")

    match_ids = get_match_ids_by_puuid(puuid, region, count=1)
    if not match_ids:
        raise ValueError("No recent matches were found for this account.")

    match_id = match_ids[0]
    match_detail = get_match_detail(match_id, region)
    if not match_detail:
        raise ValueError("Match detail could not be retrieved.")

    return extract_player_match_summary(match_detail, puuid)


def get_recent_matches_by_riot_id(
    game_name: str,
    tag_line: str,
    region: str,
    count: int = 5,
    start: int = 0,
) -> List[Dict[str, Any]]:
    # Clamp count instead of raising error.
    # This prevents the AI from crashing the tool if it asks for too many games.
    try:
        count = int(count)
    except Exception:
        count = 5

    count = max(1, min(count, 10))

    account = get_account_by_riot_id(game_name, tag_line, region)
    if not account:
        raise ValueError("Riot account was not found.")

    puuid = account.get("puuid")
    if not puuid:
        raise ValueError("PUUID was not found for this Riot account.")

    match_ids = get_match_ids_by_puuid(puuid, region, start=start, count=count)
    if not match_ids:
        return []

    summaries: List[Dict[str, Any]] = []

    for match_id in match_ids:
        match_detail = get_match_detail(match_id, region)
        if not match_detail:
            continue

        try:
            summaries.append(extract_player_match_summary(match_detail, puuid))
        except Exception:
            continue

    return summaries


def get_match_detail_by_riot_id(
    game_name: str,
    tag_line: str,
    region: str,
    match_id: str,
) -> Dict[str, Any]:
    account = get_account_by_riot_id(game_name, tag_line, region)
    if not account:
        raise ValueError("Riot account was not found.")

    puuid = account.get("puuid")
    if not puuid:
        raise ValueError("PUUID was not found for this Riot account.")

    match_detail = get_match_detail(match_id, region)
    if not match_detail:
        raise ValueError("Match detail could not be retrieved.")

    return extract_player_match_summary(match_detail, puuid)