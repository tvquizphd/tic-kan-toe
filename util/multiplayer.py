from fastapi import WebSocket
from functools import lru_cache
from util.models import Message
from util.models import MessageState
from util.models import from_message
from util.models import to_message
import threading
import queue
import json
import sys

def to_latest_history(history, item):
    for k_v in history[::-1]:
        if not k_v: continue
        k, v = k_v
        if k == item.user_id:
            return k,v
        if isinstance(k, tuple):
            if item.user_id in k:
                return k,v
    return None

def to_candidate_key(item):
    ws_state = item.ws_state
    candidate_key = ({
        MessageState.leader: MessageState.trainer,
        MessageState.trainer: MessageState.leader
    }).get(ws_state, ws_state)
    return candidate_key

def to_candidate_dict(memory, item):
    candidate_key = to_candidate_key(item)
    candidates = memory.get(candidate_key , {})
    return candidate_key, candidates

def matches_by_max_gen(candidate_key, candidates, item):
    ws_state = item.ws_state
    if candidate_key == MessageState.battle:
        for k,v in candidates.items():
            if item.user_id in k:
                yield (k,v)
        return
    # Match candidates
    compare = ({
        MessageState.leader: lambda own, other: own >= other,
        MessageState.trainer: lambda own, other: other >= own
    }).get(ws_state, lambda own, other: True)
    for (k,v) in candidates.items():
        if compare(item.max_gen, v.max_gen):
            yield (k, v)

def del_if(d, k):
    if k in d: del d[k]

def mutate_memory(memory, item):
    own_id = item.user_id
    own_kind = memory[item.ws_state]
    battles = memory[MessageState.battle]
    def clear_battles(k1, k2):
        for bk in list(battles.keys()):
            if k1 in bk or k2 in bk:
                del_if(battles, bk)
    candidate_key, candidates = (
        to_candidate_dict(memory, item)
    )
    matches = list(matches_by_max_gen(
        candidate_key, candidates, item
    ))
    is_battle = (
        candidate_key == MessageState.battle
    )
    is_leader = not is_battle and (
        candidate_key != MessageState.leader
    )
    if is_battle:
        # Stop battle, go offline
        if not len(matches):
            item.is_on = False
            item.ws_state = (
                MessageState.leader
            )
            return (
                own_id, item
            )
        # Only one battle at once
        for k,_ in matches[1:]:
            del_if(battles, k)
        k = matches[0][0]
        # Allow client-side validation
        item.group_ids = list(k)
        battles[k] = item
        # TODO -- handle conflicts
        # TODO -- "grid_action"
        return (
            k, item
        )
    elif len(matches):
        k, v = matches[0]
        # Clear non-battles
        del_if(own_kind, k)
        del_if(candidates, k)
        del_if(own_kind, own_id)
        del_if(candidates, own_id)
        # Clear battles
        clear_battles(k, own_id)
        # Leader is always right!
        battle_id = (
            k if is_leader else own_id,
            own_id if is_leader else k
        )
        battles[battle_id] = (
            item if is_leader else v
        )
        item.is_on = True
        item.group_ids = list(
            battle_id
        )
        item.ws_state = (
            MessageState.battle
        )
        return (
            battle_id, item
        )
    # Just update own status
    own_kind[own_id] = item
    # Handle any transitions
    del_if(candidates, own_id)
    item.is_on = True
    return (
        own_id, item 
    )


def start_worker(q, history):
    # battle: Two user keys
    # leader, trainer: One user key
    memory_lock = threading.Lock()
    memory = {
        MessageState.battle: dict(),
        MessageState.leader: dict(),
        MessageState.trainer: dict()
    }
    # Worker
    def worker():
        while True:
            item = q.get()
            if (q.qsize()):
                print(f'{q.q_size()} messages in queue')
            history.pop(0)
            with memory_lock:
                history.append(mutate_memory(
                    memory, item
                ))
            q.task_done()
    # Start worker
    threading.Thread(
        target=worker, daemon=True
    ).start()

class Multiplayer:
    def __init__(self):
        self.__user_ids = dict()
        self.__users: list[WebSocket] = []
        self.HISTORY = [
            None for _ in range(100)
        ]
        self.Q = queue.Queue(maxsize=20)
        # Start the worker daemon
        start_worker(self.Q, self.HISTORY)
    
    @property
    def users(self) -> list[WebSocket]:
        return self.__users

    def running(self, user: WebSocket) -> bool:
        return user.client_state.CONNECTED
    
    async def connect(self, user: WebSocket):
        await user.accept()
        self.__users.append(user)

    def untrack_user(self, user: WebSocket):
        self.__users.remove(user)

    async def send_text(self, data: str):
        for user in self.users:
            if not self.running(user):
                continue
            try:
                await user.send_text(data)
            except RuntimeError as e:
                print(repr(e), file=sys.stderr)
                pass

    async def send_message(self, message: Message):
        await self.send_text(from_message(message))

    async def use_message(self, user: WebSocket) -> Message:
        # TODO: should cache user_id in self.__user_ids
        message = to_message(await user.receive_text()) 
        self.Q.put(message)
        self.Q.join()
        latest = to_latest_history(
            self.HISTORY, message
        )
        if not latest: return message
        key, broadcast = latest
        print(f'Updating {key}')
        return broadcast

@lru_cache()
def to_multiplayer():
    return Multiplayer()
