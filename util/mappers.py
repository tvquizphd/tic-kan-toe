from typing import (
    Dict, List, Callable
)
from pydantic import BaseModel

class Mappers(BaseModel):
    alphabet_list: List[str]
    arpepet_list: List[str]
    arpepet_table: Dict[str, str]
    arpepet_vowels: List[List[str]]
    arpepet_consonants: List[List[str]]
    arpepet_ngram_lists: Dict[int, List[str]]
    alphabet_ngram_lists: Dict[int, List[str]]
    ipa_to_arpabet: Callable[[str], List[str]]
    alphabet_to_arpabet: Callable[[str], List[str]]

