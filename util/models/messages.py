from pydantic import BaseModel
from enum import Enum, IntEnum
from typing import Annotated
from typing import Optional
import json

class MessageState(str, Enum):
    battle = 'found'
    leader = 'hosting'
    trainer = 'finding'
    quitter = 'leaving'

class ActionContent(BaseModel):
    generation: int
    name: str
    key: int
    id: int

class Action(BaseModel):
    content: ActionContent
    position: int

class GridState(BaseModel):
    contents: Annotated[
        list[Optional[ActionContent]],
    9] 
    cols: Annotated[list[str], 3]
    rows: Annotated[list[str], 3]

class Message(BaseModel):
    is_on: bool
    max_gen: int
    user_id: str
    badge_offer: int
    group_ids: list[str]
    grid_state: GridState
    grid_action: Optional[Action] = None
    ws_state: MessageState

def to_message(text) -> Message:
    obj = json.loads(text)
    return Message(**obj)

def from_message(message: Message):
    return json.dumps(message.dict())
