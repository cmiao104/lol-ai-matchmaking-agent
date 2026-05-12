from typing import Optional, Dict, Any
from google.cloud import firestore

PROJECT_ID = "bright-calculus-485601-g6"

db = firestore.Client(project=PROJECT_ID)


def get_riot_binding(discord_user_id: str) -> Optional[Dict[str, Any]]:
    doc_ref = db.collection("riot_bindings").document(str(discord_user_id))
    doc = doc_ref.get()

    if not doc.exists:
        return None

    return doc.to_dict()