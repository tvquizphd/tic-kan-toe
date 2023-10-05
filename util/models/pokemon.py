from pydantic import BaseModel
from typing import Optional

class Pokemon(BaseModel):
    percentage: int
    name: str
    dex: int

class HasPokemon(BaseModel):
    pokemon: Pokemon
