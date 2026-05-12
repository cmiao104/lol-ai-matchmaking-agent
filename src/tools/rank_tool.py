import json
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CACHE_PATH = BASE / "data" / "rank_cache.json"

TIER_BASE = {
    "IRON": 0,
    "BRONZE": 400,
    "SILVER": 800,
    "GOLD": 1200,
    "PLATINUM": 1600,
    "EMERALD": 2000,
    "DIAMOND": 2400,
    "MASTER": 2800,
    "GRANDMASTER": 3200,
    "CHALLENGER": 3600,
}

RANK_BASE = {
    "IV": 0,
    "III": 100,
    "II": 200,
    "I": 300,
}


def rank_score(tier: str, rank: str = "IV", lp: int = 0) -> float:
    tier = (tier or "").upper()
    rank = (rank or "IV").upper()

    return TIER_BASE.get(tier, -1) + RANK_BASE.get(rank, 0) + lp / 100


def load_rank_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}

    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rank_cache(cache: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_cached_rank(puuid: str) -> dict | None:
    cache = load_rank_cache()
    return cache.get(puuid)


def upsert_rank_cache(
    puuid: str,
    region: str,
    tier: str,
    rank: str,
    league_points: int = 0,
    queue_type: str = "RANKED_SOLO_5x5",
):
    cache = load_rank_cache()

    cache[puuid] = {
        "puuid": puuid,
        "region": region,
        "queue_type": queue_type,
        "tier": tier,
        "rank": rank,
        "league_points": league_points,
        "rank_score": rank_score(tier, rank, league_points),
        "updated_at": int(time.time()),
    }

    save_rank_cache(cache)
    return cache[puuid]


def filter_puuids_by_rank_window(
    candidate_puuids: list[str],
    user_puuid: str,
    window: int = 400,
) -> list[str]:
    cache = load_rank_cache()

    user_rank = cache.get(user_puuid)
    if not user_rank:
        return candidate_puuids

    my_score = user_rank["rank_score"]

    valid = []

    for puuid in candidate_puuids:
        r = cache.get(puuid)
        if not r:
            continue

        if abs(r["rank_score"] - my_score) <= window:
            valid.append(puuid)

    return valid