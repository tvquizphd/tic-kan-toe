from fastapi import WebSocket
from functools import lru_cache
from util.models import Message
from util.models import MessageState
from util.models import from_message
from util.models import to_message
from pydantic import BaseModel
from typing import Any, Optional
import threading
from uuid import uuid4
import queue
import json
import sys

class User(BaseModel):
    client: Any # WebSocket
    user_id: Optional[str]

class QueueAction(BaseModel):
    forget: bool
    user_id: str

class QueueItem(BaseModel):
    message: Optional[Message]
    meta: Optional[QueueAction]

def to_latest_history(history, message):
    for k_v in history[::-1]:
        if not k_v: continue
        k, v = k_v
        if k == message.user_id:
            return k,v
        if isinstance(k, tuple):
            if message.user_id in k:
                return k,v
    return None

def to_relative_state(message):
    ws_state = message.ws_state
    relative_state = ({
        MessageState.leader: MessageState.trainer,
        MessageState.trainer: MessageState.leader,
        MessageState.quitter: MessageState.battle
    }).get(ws_state, ws_state)
    return relative_state

def to_relative_dict(memory, message):
    relative_state = to_relative_state(message)
    relatives = memory.get(relative_state , {})
    return relative_state, relatives

def matches_by_max_gen(relative_state, relatives, message):
    ws_state = message.ws_state
    if relative_state == MessageState.battle:
        for k,v in relatives.items():
            if message.user_id in k:
                yield (k,v)
        return
    # Match relatives
    compare_gen = ({
        MessageState.leader: lambda own, other: own >= other,
        MessageState.trainer: lambda own, other: other >= own
    }).get(ws_state, lambda own, other: True) # TODO consider own == other
    for (k,v) in relatives.items():
        if compare_gen(message.max_gen, v.max_gen):
            yield (k, v)

def del_if(d, k):
    if k in d: del d[k]

def clear_all_battles(memory, k1, k2=None):
    battles = memory[MessageState.battle]
    for bk in list(battles.keys()):
        if k1 in bk or k2 in bk:
            del_if(battles, bk)

def clear_from_all(memory, k):
    battles = memory[MessageState.battle]
    leaders = memory[MessageState.leader]
    trainers = memory[MessageState.trainer]
    if isinstance(k, tuple):
        return del_if(battles, k)
    clear_all_battles(memory, k)
    del_if(trainers, k)
    del_if(leaders, k)

def mutate_memory(memory, message):
    own_id = message.user_id
    own_state = message.ws_state
    # Corresponding other dictionary
    relative_state, relatives = (
        to_relative_dict(memory, message)
    )
    # Wanting to end battle
    is_quitter = (
        own_state == MessageState.quitter
    )
    # Actively in existing battle
    is_battle = is_quitter or (
        own_state == MessageState.battle
    )
    # Don't find self!
    if not is_battle:
        del_if(relatives, own_id)
    # Match leaders and trainers
    matches = list(matches_by_max_gen(
        relative_state, relatives, message
    ))
    no_matches = not len(matches)
    clear_from_all(memory, own_id)
    if is_battle:
        if no_matches:
            # Transition self to leader
            new_state = MessageState.leader
            new_kind = memory[new_state]
            message.group_ids = [ own_id ]
            message.ws_state = new_state
            new_kind[own_id] = message
            return ( own_id, message )
        pair = matches[0][0]
        # Stop tracking
        if is_quitter:
            message.is_on = False
            clear_all_battles(memory, *pair)
            message.group_ids = list(pair)
            return ( own_id, message )
        # Only one battle at once
        for _pair,_ in matches[1:]:
            clear_all_battles(memory, *_pair)
        # TODO -- handle conflicts
        # TODO -- using "grid_action"
        # Save and return battle
        message.group_ids = list(pair)
        battles = memory[MessageState.battle]
        battles[pair] = message
        return (pair, message)
    # Update own record
    if no_matches:
        # Update own record 
        message.group_ids = [own_id]
        own_kind = memory[own_state]
        own_kind[own_id] = message
        return (
            own_id, message 
        )
    # Check existing battles
    battles = memory[MessageState.battle]
    battle_matches = list(matches_by_max_gen(
        MessageState.battle, battles, message
    ))
    # Is hosting
    is_leader = (
        own_state == MessageState.leader
    )
    if (len(battle_matches)):
        battle_id, battle_message = battle_matches[0]
        for pair,_ in matches[1:]:
            del_if(battles, pair)
        battle_message.badge_offer = (
            message.badge_offer if is_leader
            else battle_message.badge_offer
        )
        battles[battle_id] = battle_message
        return (
            battle_id, battle_message
        )
    # Find first matching relative
    match_id, match_message = matches[0]
    clear_all_battles(memory, match_id, own_id)
    clear_from_all(memory, match_id)
    # Leader is always right!
    message = (
        message if is_leader else match_message
    )
    message.group_ids = [
        (match_id if is_leader else own_id),
        (own_id if is_leader else match_id)
    ]
    # Start, save, and return battle
    message.ws_state = (MessageState.battle)
    battle_id = tuple(message.group_ids)
    battles[battle_id] = message
    return (battle_id, message)

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
            q_item = q.get()
            if (q.qsize()):
                print(f'{q.q_size()} messages in queue')
            history.pop(0)
            with memory_lock:
                if q_item.message != None:
                    # Handle queue message
                    history.append(mutate_memory(
                        memory, q_item.message
                    ))
                if q_item.meta == None:
                    q.task_done()
                    continue
                action = q_item.meta
                if not action.forget:
                    q.task_done()
                    continue
                k = action.user_id
                # Clear memory and history
                clear_from_all(memory, k)
                for hi,h in enumerate(history):
                    if h is None: continue
                    if k == h[0] or k in h[0]:
                        history[hi] = None
                q.task_done()
                continue

    # Start worker
    threading.Thread(
        target=worker, daemon=True
    ).start()

Q_LEN = 20
HISTORY_LEN = 100

class Multiplayer:
    def __init__(self):
        # Mutated by this class instance
        self.user_lock = threading.Lock()
        self.user_dict: dict[str,User] = {}
        # Q and HISTORY only mutated by daemon
        self.Q = queue.Queue(maxsize=Q_LEN)
        self.HISTORY = [
            None for _ in range(HISTORY_LEN)
        ]
        # Start the worker daemon
        start_worker(self.Q, self.HISTORY)
    
    @property
    def users(self) -> list[User]:
        return self.user_dict.values()

    @property
    def clients(self) -> list[WebSocket]:
        return [ user.client for user in self.users ]

    def running(self, client: WebSocket) -> bool:
        return client.client_state.CONNECTED
    
    async def connect(self, client: WebSocket):
        await client.accept()
        with self.user_lock:
            uuid = str(uuid4())
            self.user_dict[uuid] = (
                User(client=client)
            )

    def untrack_client(self, client: WebSocket):
        # Track any matching users
        untracked_users = {}
        # Track all clients for deletion
        for uuid, user in [*self.user_dict.items()]:
            # Delete the client's user from list
            if user.client != client: continue
            untracked_users[uuid] = user
        # Delete all untracked users
        for uuid, user in untracked_users.items():
            with self.user_lock:
                del_if(self.user_dict, uuid)
            # Schedule to forget user
            if not user.user_id: continue
            action = QueueAction(**{
                'user_id': user.user_id,
                'forget': True
            })
            self.Q.put(QueueItem(meta=action))

    async def send_text(self, data: str):
        for user in self.users:
            if not self.running(user.client):
                continue
            try:
                await user.client.send_text(data)
            except RuntimeError as e:
                print(repr(e), file=sys.stderr)
                pass

    async def send_message(self, message: Message):
        await self.send_text(from_message(message))

    async def use_message(self, client: WebSocket) -> Message:
        message = to_message(await client.receive_text()) 
        # Associate message user id with client 
        for user in self.users:
            if user.client != client: continue
            if user.user_id: continue
            with self.user_lock:
                user.user_id = message.user_id
        # Handle the message
        self.Q.put(QueueItem(message=message))
        self.Q.join()
        latest = to_latest_history(
            self.HISTORY, message
        )
        if not latest: return message
        key, broadcast = latest
        print(
            f'From: {message.group_ids}', message.ws_state
        )
        print(
            f'To: {broadcast.group_ids}', broadcast.ws_state
        )
        return broadcast

@lru_cache()
def to_multiplayer():
    return Multiplayer()
