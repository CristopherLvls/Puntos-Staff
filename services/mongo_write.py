"""Persistencia de evaluaciones en Cluster0."""

from datetime import datetime, timezone

from pymongo import MongoClient, ReturnDocument
from pymongo.database import Database

import config

_client: MongoClient | None = None


def get_write_db() -> Database:
    global _client
    if _client is None:
        if not config.MONGODB_WRITE_URI:
            raise RuntimeError("MONGODB_WRITE_URI no configurada")
        _client = MongoClient(config.MONGODB_WRITE_URI, serverSelectionTimeoutMS=10000)
        db = _client[config.MONGODB_WRITE_DB]
        db["evaluations"].create_index([("staff_discord_id", 1), ("created_at", -1)])
        db["staff_scores"].create_index("staff_discord_id", unique=True)
    return _client[config.MONGODB_WRITE_DB]


def save_evaluation(data: dict) -> str:
    db = get_write_db()
    result = db["evaluations"].insert_one(data)
    _update_staff_score(data)
    return str(result.inserted_id)


def _update_staff_score(evaluation: dict) -> None:
    db = get_write_db()
    staff_id = evaluation["staff_discord_id"]
    points = evaluation["points"]

    updated = db["staff_scores"].find_one_and_update(
        {"staff_discord_id": staff_id},
        {
            "$inc": {"total_points": points, "evaluation_count": 1},
            "$set": {
                "staff_display_name": evaluation.get("staff_display_name", ""),
                "last_reputation_status": evaluation.get("reputation_status", ""),
                "last_evaluated_at": evaluation.get("created_at"),
                "last_role": evaluation.get("role", ""),
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    count = updated.get("evaluation_count", 1)
    total = updated.get("total_points", points)
    avg = round(total / count, 2) if count else points

    db["staff_scores"].update_one(
        {"staff_discord_id": staff_id},
        {"$set": {"average_points": avg}},
    )


def get_staff_score(staff_discord_id: str) -> dict | None:
    db = get_write_db()
    return db["staff_scores"].find_one({"staff_discord_id": staff_discord_id})


def get_evaluation_history(staff_discord_id: str, limit: int = 10) -> list[dict]:
    db = get_write_db()
    cursor = (
        db["evaluations"]
        .find({"staff_discord_id": staff_discord_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return list(cursor)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
