"""Cliente de solo lectura para la BD de SirgioBOT."""

from pymongo import MongoClient
from pymongo.database import Database

import config

_client: MongoClient | None = None


def get_read_db() -> Database:
    global _client
    if _client is None:
        if not config.MONGODB_READONLY_URI:
            raise RuntimeError("MONGODB_READONLY_URI no configurada")
        _client = MongoClient(config.MONGODB_READONLY_URI, serverSelectionTimeoutMS=10000)
    return _client[config.MONGODB_READONLY_DB]


class ReadOnlyCollection:
    """Wrapper que solo expone operaciones de lectura."""

    def __init__(self, collection):
        self._col = collection

    def find(self, *args, **kwargs):
        return self._col.find(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    def aggregate(self, *args, **kwargs):
        return self._col.aggregate(*args, **kwargs)

    def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    def distinct(self, *args, **kwargs):
        return self._col.distinct(*args, **kwargs)


def get_logs_collection() -> ReadOnlyCollection:
    db = get_read_db()
    return ReadOnlyCollection(db[config.MONGODB_LOGS_COLLECTION])
