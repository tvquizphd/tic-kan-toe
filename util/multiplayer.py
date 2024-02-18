from functools import lru_cache
from fastapi import WebSocket
import json
import sys

class Multiplayer:
    def __init__(self):
        self.__users: list[WebSocket] = []
    
    @property
    def users(self) -> list[WebSocket]:
        return self.__users

    def running(self, user: WebSocket) -> bool:
        return user.client_state.CONNECTED
    
    async def connect(self, user: WebSocket):
        await user.accept()
        self.__users.append(user)

    async def disconnect(self, user: WebSocket):
        await user.close()
        self.__users.remove(user)

    async def send_text(self, data: str):
        for user in self.__users:
            if not self.running(user): continue
            try:
                await user.send_text(data)
            except RuntimeError as e:
                print(repr(e), file=sys.stderr)
                pass

    async def send_json(self, data: dict):
        self.send_text(json.dumps(data))

@lru_cache()
def to_multiplayer():
    return Multiplayer()
