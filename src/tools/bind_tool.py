from typing import Dict, Any
from services.riot_bind_store import get_riot_binding


def get_bound_riot_account(discord_user_id: str) -> Dict[str, Any]:
    try:
        data = get_riot_binding(discord_user_id)

        if not data:
            return {
                "success": False,
                "error": "No Riot account is bound to this Discord user."
            }

        return {
            "success": True,
            "discord_user_id": discord_user_id,
            "game_name": data.get("game_name"),
            "tag_line": data.get("tag_line"),
            "platform": data.get("platform", "na1"),
            "region": data.get("region"),
            "puuid": data.get("puuid"),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }