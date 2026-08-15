import json

from app.database import SessionLocal
from app.models.asset import Asset
from app.services.dialogue_corrector import (
    apply_dialogue_decisions,
    recover_uncertain_dialogues,
)

ASSET_ID = "dbfd9f79-f749-4620-9c25-7033d82b65a2"

db = SessionLocal()

try:
    asset = (
        db.query(Asset)
        .filter(Asset.id == ASSET_ID)
        .first()
    )

    if not asset:
        raise RuntimeError("Asset not found")

    if not asset.dialogues:
        raise RuntimeError("Asset has no dialogues")

    dialogues = json.loads(asset.dialogues)

    # Bước 1: Decision Engine
    decided = apply_dialogue_decisions(dialogues)

    print("\n=== BEFORE RECOVERY ===")
    for dialogue in decided:
        print(
            dialogue.get("region_id"),
            "->",
            dialogue.get("decision"),
            "|",
            dialogue.get("clean_text"),
        )

    # Bước 2: Auto-Recovery
    recovered = recover_uncertain_dialogues(
        image_path=asset.file_path,
        dialogues=decided,
    )

    print("\n=== AFTER RECOVERY ===")
    print(
        json.dumps(
            recovered,
            ensure_ascii=False,
            indent=2,
        )
    )

finally:
    db.close()
