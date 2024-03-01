from fastapi import WebSocket
from functools import lru_cache
from models import Message
from models import MessageState
from models import from_message
from models import to_message
from pydantic import BaseModel
from typing import Any, Optional
import threading
from uuid import uuid4
import copy
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

def history_update(history, memory, q_item):
    if q_item.message == None:
        return
    updates = memory_update(
        memory, q_item.message
    )
    for update in updates:
        history.pop(0)
        history.append(update)

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

def clear_all_battles(memory, k1, k2=None):
    battles = memory[MessageState.battle]
    for bk in list(battles.keys()):
        if k1 in bk or k2 in bk:
            del_if(battles, bk)

def clear_all_battles_etc(memory, pair):
    keys = [ [pair], list(pair) ][
        int(isinstance(pair, tuple))
    ]
    clear_all_battles(memory, *keys)
    # Clear affiliated trainers and leaders
    leaders = memory[MessageState.leader]
    trainers = memory[MessageState.trainer]
    for k in keys:
        del_if(trainers, k)
        del_if(leaders, k)

def memory_clear(memory, k):
    clear_all_battles_etc(memory, k)

def simple_update(memory, message, k, new_state):
    is_pair = isinstance(k, tuple)
    message = copy.deepcopy(message)
    message.group_ids = (
        list(k) if is_pair else [ k ]
    )
    if not is_pair:
        message.user_id = k
    message.ws_state = new_state
    memory[new_state][k] = message
    return (k, message)

def battle_update(memory, message, pair):
    new_state = MessageState.battle
    return simple_update(
        memory, message, pair, new_state
    )

def leader_update(memory, message, k):
    new_state = MessageState.leader
    return simple_update(
        memory, message, k, new_state
    )

def memory_update(memory, message):
    own_k = message.user_id
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
        del_if(relatives, own_k)
    # Match first compatible record 
    matches = list(matches_by_max_gen(
        relative_state, relatives, message
    ))
    # Clears associated battles, etc
    memory_clear(memory, own_k)
    if is_battle:
        if not len(matches):
            return [
                leader_update(memory, message, own_k)
            ]
        if is_quitter:
            return [
                leader_update(memory, message, k)
                for k in matches[0][0]
            ]
        # TODO -- handle battle conflicts
        # TODO -- using "grid_action"
        if (message.grid_action):
            print('Action')
            print(
                message.grid_action.content.name,
                message.grid_action.position
            )
        return [
            battle_update(memory, message, matches[0][0])
        ] 
    if not len(matches):
        return [
            simple_update(memory, message, own_k, own_state)
        ]
    # Handle first matching relative
    memory_clear(memory, matches[0][0])
    match_id, match_message = matches[0]
    # Leader is always right!
    battle_k, message = [
        [(own_k, match_id), match_message],
        [(match_id, own_k), message]
    ][int(
        own_state == MessageState.leader
    )]
    # Create a new battle
    return [
        battle_update(memory, message, battle_k)
    ] 

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
        group_ids = [*message.group_ids]
        print(
            f'From: {group_ids}', message.ws_state
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
        # Send all unique messages
        def find_history(k):
            k_v = search_history(self.HISTORY, k)
            if not k_v: return []
            return [k_v[1]]
        unique_messages = ({
            tuple(message.group_ids): message
            for k in group_ids for message in 
            find_history(k)
        }).values()
        for broadcast in unique_messages:
            await self.send_message(broadcast)

@lru_cache()
def to_multiplayer():
    return Multiplayer()
