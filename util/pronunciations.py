import re
from typing import (
    Dict, List 
)
import wikitextparser as wtp
from pydantic import BaseModel
from .config import get_api
from .syllables import (
    match_syllables, invent_syllables
)
from .match_bits import to_match_bits
from .arpepet import (
    alphabet_to_arpepet, ipa_to_arpepet
)


class Pronunciation(BaseModel):
    id: int
    alphabet_match_bits: Dict[int,int]
    arpepet_match_bits: Dict[int,int]
    syllable_phones: List[str]
    phones: str


def get_raw(guide, url):
    return get_api(guide, f'{url}?action=raw', 'text')


def find_generation_pages(guide):
    guide_text = get_raw(guide, '')
    pattern = r'\* \[\[/Generation (\w+)\|Generation \1\]\]'
    matches = re.findall(pattern, guide_text)
    yield from [
        get_raw(guide, f'/Generation_{numeral}')
        for numeral in matches
    ]


def parse_generation_page(page_text, mappers):
    return [
        page_to_pronunciation(mappers, t.arguments)
        for t in wtp.parse(page_text).templates
        if len(t.arguments) in { 7, 8 }
    ]


def to_alphabet_bigram_bits(mappers, vals):
    return sum(
        to_match_bits(
            2, q.lower(),
            mappers.alphabet_ngram_lists[2], {}
        )
        for q in vals
    )


def to_arpepet_4gram_bits(mappers, vals):
    return sum(
        to_match_bits(
            4, q.lower(),
            mappers.arpepet_ngram_lists[4], {}
        )
        for q in vals
    )


def page_to_pronunciation(mappers, args):
    respelled_syllables = args[5].value.lower().split('-')
    arpepet_of_eng_syllables = [
        alphabet_to_arpepet(mappers, syllable)
        for syllable in respelled_syllables
    ]
    arpepet_of_ipa_words = [
        ipa_to_arpepet(mappers, ipa_word)
        for ipa_word in args[6].value.split(' ')
    ]
    arpepet_syllables = match_syllables(
        arpepet_of_eng_syllables,
        arpepet_of_ipa_words,
    )
    alphabet_bigram_bits = to_alphabet_bigram_bits(
        mappers, [
            q for idx in [1, 3, 5]
            for q in args[idx].value.split('-')
        ]
    )
    arpepet_4gram_bits = to_arpepet_4gram_bits(
        mappers, [ ''.join(arpepet_syllables) ]
    )
    return Pronunciation(
        id=int(args[0].value),
        syllable_phones=arpepet_syllables,
        phones=''.join(arpepet_syllables),
        alphabet_match_bits={
            2: alphabet_bigram_bits
        },
        arpepet_match_bits={
            4: arpepet_4gram_bits 
        }
    )


def mon_to_pronunciation(mappers, reviewers, mon):
    arpepet_syllables = [
        ''.join(alphabet_to_arpepet(
            mappers, syllable
        ))
        for syllable in mon.name.split('-') 
    ]
    # Most common case: no dash in name
    if len(arpepet_syllables) == 1:
        arpepet_syllables = invent_syllables(
            reviewers,  arpepet_syllables[0],
            max_syllables=3
        )
    alphabet_bigram_bits = to_alphabet_bigram_bits(
        mappers, [ mon.name ]
    )
    arpepet_4gram_bits = to_arpepet_4gram_bits(
        mappers, [ ''.join(arpepet_syllables) ]
    )
    return Pronunciation(
        id=mon.id,
        syllable_phones=arpepet_syllables,
        phones=''.join(arpepet_syllables),
        alphabet_match_bits={
            2: alphabet_bigram_bits
        },
        arpepet_match_bits={
            4: arpepet_4gram_bits 
        }
    )


def find_pronunciations(
        fandom, mappers
    ):
    pages = list(find_generation_pages(
        f'{fandom}/wiki/Pokémon_Pronunciation_Guide'
    ))
    return {
        name.id: name for page in pages
        for name in parse_generation_page(
            page, mappers
        )
    }
