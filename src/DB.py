import os
import random
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient


class UserDatabase:
    def __init__(self):
        load_dotenv()

        self.client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.client[os.getenv("MONGO_DB")]
        self.users = self.db[os.getenv("MONGO_COLLECTION")]

        self.users.create_index("id", unique=True)
        self.users.create_index(
            "lastLogin",
            expireAfterSeconds=30 * 24 * 60 * 60
        )

    def _generateId(self):
        while True:
            user_id = random.randint(100000000, 999999999)

            if not self.users.find_one({"id": user_id}):
                return user_id

    def addUser(self, name: str):
        now = datetime.now(timezone.utc)

        user = {
            "id": self._generateId(),
            "name": name,
            "creationTime": now,
            "lastLogin": now,
            "saves": {}
        }

        self.users.insert_one(user)

        user.pop("_id", None)

        return user

    def getUser(self, user_id: int):
        return self.users.find_one(
            {"id": user_id},
            {"_id": 0}
        )

    def login(self, user_id: int):
        self.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "lastLogin": datetime.now(timezone.utc)
                }
            }
        )

    def addSave(self, user_id: int, save_name: str, stocks: dict):
        self.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    f"saves.{save_name}": stocks
                }
            }
        )

    def getSave(self, user_id: int, save_name: str):
        user = self.getUser(user_id)

        if not user:
            return None

        return user["saves"].get(save_name)

    def deleteSave(self, user_id: int, save_name: str):
        self.users.update_one(
            {"id": user_id},
            {
                "$unset": {
                    f"saves.{save_name}": ""
                }
            }
        )