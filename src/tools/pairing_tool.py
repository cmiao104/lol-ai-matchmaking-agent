import json
from pathlib import Path

import joblib
import pandas as pd

from tools.riot_identity_tool import get_riot_id_by_puuid, get_rank_by_puuid

BASE = Path(__file__).resolve().parents[1]

MODEL_PATH = BASE / "models" / "best_pair_model_group_v2_role_specific.pkl"
META_PATH = BASE / "models" / "best_pair_model_group_v2_role_specific_features.json"
DATA_PATH = BASE / "data" / "player_role_profiles_group_train.parquet"

model = None
meta = None
profiles = None


def load_assets():
    global model, meta, profiles

    if model is None:
        model = joblib.load(MODEL_PATH)

    if meta is None:
        with open(META_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)

    if profiles is None:
        profiles = pd.read_parquet(DATA_PATH)

    return model, meta, profiles


def build_pair_row(a, b):
    row = {}

    row["role_a"] = str(a.get("role", "unknown"))
    row["role_b"] = str(b.get("role", "unknown"))
    row["same_role"] = int(row["role_a"] == row["role_b"])
    row["role_pair"] = f'{row["role_a"]}_{row["role_b"]}'
    row["role_pair_sorted"] = "_".join(sorted([row["role_a"], row["role_b"]]))

    for col in a.index:
        if col in ["puuid", "role", "main_flash_slot"]:
            continue

        av = pd.to_numeric(a.get(col, 0), errors="coerce")
        bv = pd.to_numeric(b.get(col, 0), errors="coerce")

        if pd.isna(av):
            av = 0.0
        if pd.isna(bv):
            bv = 0.0

        av = float(av)
        bv = float(bv)

        row[f"a_{col}"] = av
        row[f"b_{col}"] = bv
        row[f"diff_{col}"] = av - bv
        row[f"absdiff_{col}"] = abs(av - bv)
        row[f"mean_{col}"] = (av + bv) / 2
        row[f"prod_{col}"] = av * bv

    row["a_main_flash_slot"] = str(a.get("main_flash_slot", "unknown"))
    row["b_main_flash_slot"] = str(b.get("main_flash_slot", "unknown"))

    return row


def _format_player_name(puuid: str, routing: str = "americas") -> str:
    identity = get_riot_id_by_puuid(puuid=puuid, routing=routing)

    if "error" in identity:
        return "Unknown Player"

    game_name = identity.get("game_name")
    tag_line = identity.get("tag_line")

    if game_name and tag_line:
        return f"{game_name}#{tag_line}"

    return "Unknown Player"


def _get_rank(puuid: str, platform: str = "na1") -> dict:
    rank = get_rank_by_puuid(puuid=puuid, platform=platform)

    return {
        "rank_text": rank.get("rank_text", "Unknown Rank"),
        "rank_score": rank.get("rank_score"),
    }


def recommend_duo(
    user_puuid: str,
    top_k: int = 5,
    sample_size: int = 500,
    platform: str = "na1",
    rank_window: int = 400,
    rank_check_top_n: int = 50,
):
    model, meta, df = load_assets()

    feature_cols = meta["feature_cols"]
    cat_cols = meta.get("categorical_cols", [])

    mine = df[df["puuid"] == user_puuid]

    if mine.empty:
        return {"error": "User profile not found"}

    mine = mine.sort_values("games_played", ascending=False).head(1)
    a = mine.iloc[0]

    user_rank = _get_rank(user_puuid, platform=platform)
    user_rank_score = user_rank.get("rank_score")

    others = df[
        (df["puuid"] != user_puuid) &
        (df["games_played"] >= 10)
    ].copy()

    others = (
        others.sort_values(["puuid", "games_played"], ascending=[True, False])
        .drop_duplicates("puuid")
    )

    if len(others) > sample_size:
        others = others.sample(n=sample_size, random_state=42)

    rows = []
    refs = []

    for _, b in others.iterrows():
        rows.append(build_pair_row(a, b))
        refs.append((b["puuid"], b["role"]))

    if not rows:
        return {
            "success": False,
            "error": "No candidate players available.",
        }

    X = pd.DataFrame(rows)
    X = X.reindex(columns=feature_cols, fill_value=0)

    for col in cat_cols:
        if col in X.columns:
            X[col] = X[col].fillna("unknown").astype(str)

    num_cols = [c for c in X.columns if c not in cat_cols]
    X[num_cols] = X[num_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

    probs = model.predict_proba(X)[:, 1]

    result = pd.DataFrame(refs, columns=["puuid", "role"])
    result["predicted_win_probability"] = probs

    # 先按模型分数取 top N，再查这些人的段位
    pre_rank_top = (
        result.sort_values("predicted_win_probability", ascending=False)
        .head(rank_check_top_n)
        .copy()
    )

    filtered_rows = []

    for row in pre_rank_top.to_dict(orient="records"):
        candidate_puuid = row["puuid"]
        candidate_rank = _get_rank(candidate_puuid, platform=platform)
        candidate_rank_score = candidate_rank.get("rank_score")

        can_queue = False

        if user_rank_score is not None and candidate_rank_score is not None:
            can_queue = abs(candidate_rank_score - user_rank_score) <= rank_window

        if can_queue:
            row["rank"] = candidate_rank.get("rank_text", "Unknown Rank")
            filtered_rows.append(row)

    # 如果 top 50 里一个都没有能排的，返回 top N 但明确标记没有通过段位过滤
    rank_filter_applied = True

    if filtered_rows:
        final_result = (
            pd.DataFrame(filtered_rows)
            .sort_values("predicted_win_probability", ascending=False)
            .head(top_k)
        )
    else:
        rank_filter_applied = False
        final_result = pre_rank_top.head(top_k).copy()
        final_result["rank"] = "Rank filter found no queueable candidates"

    output = []

    for row in final_result.to_dict(orient="records"):
        puuid = row["puuid"]

        output.append({
            "player": _format_player_name(puuid),
            "puuid": puuid,
            "role": row["role"],
            "rank": row.get("rank", "Unknown Rank"),
            "predicted_win_probability": round(
                float(row["predicted_win_probability"]) * 100,
                2
            ),
        })

    return {
        "success": True,
        "message": "Duo recommendations generated.",
        "user_rank": user_rank.get("rank_text", "Unknown Rank"),
        "rank_filter_applied": rank_filter_applied,
        "rank_window": rank_window,
        "rank_check_top_n": rank_check_top_n,
        "recommendations": output,
    }