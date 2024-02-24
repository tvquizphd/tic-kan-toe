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

def search_history(history, k):
    for k_v in history[::-1]:
        if not k_v: continue
        if k_v[0] == k: return k_v
        # Handle partial key match 
        if isinstance(k_v[0], tuple):
            if k in k_v[0]: return k_v
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

def pick_other(pair, k):
    return pair[int(k == pair[0])]

def del_if(d, k):
    if k in d: del d[k]

def clear_all_battles(memory, k1, k2=None):
    battles = memory[MessageState.battle]
    for bk in list(battles.keys()):
        if k1 in bk or k2 in bk:
            del_if(battles, bk)

def history_update(history, memory, q_item):
    history.pop(0)
    if q_item.message == None:
        return
    history.append(memory_update(
        memory, q_item.message
    ))

def history_clear(history, memory, k):
    # Cache the latest relevant history
    message_k_v = search_history(history, k)
    memory_clear(memory, k)
    # Notify any affiliated users
    if message_k_v and isinstance(message_k_v[0], tuple):
        message_k, message = message_k_v
        other_k = pick_other(message_k, k)
        message.user_id = other_k
        memory_clear(memory, message_k)
        q_item = QueueItem(message=message)
        history_update(history, memory, q_item)
    # Clear all relevant history
    for hi,h in enumerate(history):
        if h is None: continue
        if k == h[0] or k in h[0]:
            history[hi] = None

def memory_clear_pair(memory, pair):
    if not isinstance(pair, tuple): return
    leaders = memory[MessageState.leader]
    trainers = memory[MessageState.trainer]
    clear_all_battles(memory, *pair)
    for k in pair:
        del_if(trainers, k)
        del_if(leaders, k)

def memory_clear(memory, k):
    battles = memory[MessageState.battle]
    if isinstance(k, tuple):
        memory_clear_pair(memory, k)
        return
    for bk in [*battles.keys()]:
        if k not in bk: continue
        memory_clear_pair(memory, bk)
    trainers = memory[MessageState.trainer]
    leaders = memory[MessageState.leader]
    del_if(trainers, k)
    del_if(leaders, k)

def memory_update(memory, message):
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
    # Match first compatible record 
    matches = list(matches_by_max_gen(
        relative_state, relatives, message
    ))
    no_matches = not len(matches)
    memory_clear(memory, own_id)
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
        # TODO -- handle battle conflicts
        # TODO -- using "grid_action"
        if (message.grid_action):
            print('Action')
            print(
                message.grid_action.content.name,
                message.grid_action.position
            )
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
    battles = memory[MessageState.battle]
    # Is hosting
    is_leader = (
        own_state == MessageState.leader
    )
    # Unexpected: close any existing battles
    battle_matches = list(matches_by_max_gen(
        MessageState.battle, battles, message
    ))
    # Code should be unreachable
    for bk, _ in battle_matches:
        print(
            'Unexpected:', 'stale battles found', file=sys.stderr
        )
        del_if(battles, bk)
    # Find first matching relative
    match_id, match_message = matches[0]
    clear_all_battles(memory, match_id, own_id)
    memory_clear(memory, match_id)
    # Leader is always right!
    message = (
        message if is_leader else match_message
    )
    # Leader is always on right!
    message.group_ids = [
        (own_id, match_id),
        (match_id, own_id)
    ][int(is_leader)]
    # Start, save, and return battle
    message.ws_state = (MessageState.battle)
    battle_id = tuple(message.group_ids)
    battles[battle_id] = message
    return (battle_id, message)

def start_worker(q, history):
    # battle: Two user keys
    # leader, trainer: One user key
    lock_memory_and_history = threading.Lock()
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
                print(f'{q.qsize()} messages in queue')
            with lock_memory_and_history:
                history_update(history, memory, q_item)
            if q_item.meta == None:
                q.task_done()
                continue
            if not q_item.meta.forget:
                q.task_done()
                continue
            k = q_item.meta.user_id
            # Clear memory and history
            with lock_memory_and_history:
                history_clear(history, memory, k)
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
        self.lock_user_dict = threading.Lock()
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

    @property
    def untracked_user_ids(self) -> list[str]:
        untracked_user_ids = set()
        for item in self.HISTORY:
            if item == None: continue
            message_k, message = item
            for user_id in message.group_ids:
                untracked_user_ids.add(user_id)
        # Return all user ids not matching users
        return [
            user_id for user_id
            in list(untracked_user_ids) if not
            len(self.find_users_by_user_id(user_id))
        ]

    def find_users_by_client(
            self, client: WebSocket
        ) -> dict[str, User]:
        found_user_dict = {}
        for uuid, user in [*self.user_dict.items()]:
            if user.client != client: continue
            found_user_dict[uuid] = user
        return found_user_dict

    def find_users_by_user_id(
            self, user_id: str
        ) -> dict[str, User]:
        found_user_dict = {}
        for uuid, user in self.user_dict.items():
            if user.user_id != user_id: continue
            found_user_dict[uuid] = user
        return found_user_dict

    def find_affiliates(
            self, source_user_ids: list[str]
        ) -> dict[str, User]:
        user_ids = []
        for user_id in source_user_ids:
            message_k_v = search_history(
                self.HISTORY, user_id
            )
            if not message_k_v: continue
            message_k, message = message_k_v
            if not isinstance(message_k, tuple):
                continue
            # Find non-self affliates
            other_id = pick_other(message_k, user_id)
            user_ids.append(other_id)
        affiliate_dict = {}
        # Affiliates of any users
        for user_id in user_ids:
            affiliate_dict = {
                **affiliate_dict,
                **self.find_users_by_user_id(
                    user_id
                )
            }
        return affiliate_dict

    def running(self, client: WebSocket) -> bool:
        return client.client_state.CONNECTED
    
    async def connect(self, client: WebSocket):
        await client.accept()
        with self.lock_user_dict:
            uuid = str(uuid4())
            self.user_dict[uuid] = (
                User(client=client)
            )

    async def untrack_client(self, client: WebSocket):
        users = self.find_users_by_client(client)
        untracked_user_ids = [
            *self.untracked_user_ids,
            *[
                user.user_id for user in users.values()
                if user.user_id != None
            ]
        ]
        untracked_uuids = [
            *[uuid for uuid in users.keys()],
            *[
                uuid
                for user_id in untracked_user_ids
                for uuid in self.find_users_by_user_id(user_id).keys()
            ]
        ]
        affiliated_users = self.find_affiliates(
            untracked_user_ids
        )
        # Clear from users
        for uuid in untracked_uuids:
            with self.lock_user_dict:
                del_if(self.user_dict, uuid)
        print(f'Disconnect: {len(untracked_uuids)} users')
        # Clear from Daemon
        for user_id in untracked_user_ids:
            # Delete the clients
            print('Disconnect:', user_id)
            action = QueueAction(**{
                'user_id': user_id,
                'forget': True
            })
            self.Q.put(QueueItem(meta=action))
        # Wait for Daemon
        self.Q.join()
        # Notify any remaining affiliated users
        for user in affiliated_users.values():
            if not user.user_id: continue
            message_k_v = search_history(
                self.HISTORY, user.user_id
            )
            if not message_k_v: return
            await self.send_message(message_k_v[1])

    async def send_text(self, data: str):
        for user in self.users:
            if not self.running(user.client):
                continue
            try:
                await user.client.send_text(data)
            except RuntimeError as e:
                print(repr(e), file=sys.stderr)
                pass

    async def send_message(self, broadcast: Message):
        print(
            f'To: {broadcast.group_ids}', broadcast.ws_state
        )
        await self.send_text(from_message(broadcast))

    async def use_message(self, client: WebSocket) -> Message:
        message = to_message(await client.receive_text()) 
        print(
            f'From: {message.group_ids}', message.ws_state
        )
        # Associate message user id with client 
        for user in self.users:
            if user.client != client: continue
            if user.user_id: continue
            with self.lock_user_dict:
                user.user_id = message.user_id
        # Handle the message
        self.Q.put(QueueItem(message=message))
        self.Q.join()
        message_k_v = search_history(
            self.HISTORY, message.user_id
        )
        # Echo original input
        if not message_k_v: return message
        # Return modified input
        return message_k_v[1]

@lru_cache()
def to_multiplayer():
    return Multiplayer()
