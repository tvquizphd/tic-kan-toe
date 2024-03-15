import re
from typing import List
import wikitextparser as wtp
from pydantic import BaseModel
from .config import get_api
from .syllables import (
    match_syllables, invent_syllables
)
from .bit_sums import BitSums
from .arpepet import (
    alphabet_to_arpepet, ipa_to_arpepet
)


class Pronunciation(BaseModel):
    syllable_phones: List[str]
    bit_sums: BitSums
    phones: str
    id: int


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
    arpepet_word = ''.join(arpepet_syllables)
    alphabet_words = [
        q.lower() for idx in [1, 3, 5]
        for q in args[idx].value.split('-')
    ]
    return Pronunciation(
        id=int(args[0].value),
        phones=arpepet_word,
        syllable_phones=arpepet_syllables,
        bit_sums=mappers.sum_bits(
            alphabet_words, [arpepet_word]
        )
    )


def mon_to_pronunciation(mappers, reviewers, mon):
    arpepet_syllables = [
        ''.join(alphabet_to_arpepet(
            mappers, syllable
        ))
        for syllable in mon.name.split('-') 
    ]
    alphabet_words = [ mon.name.lower() ]
    arpepet_word = ''.join(arpepet_syllables)
    # Most common case: no dash in name
    if len(arpepet_syllables) == 1:
        arpepet_syllables = invent_syllables(
            reviewers,  arpepet_syllables[0],
            max_syllables=3
        )
    return Pronunciation(
        id=mon.id,
        phones=arpepet_word,
        syllable_phones=arpepet_syllables,
        bit_sums=mappers.sum_bits(
            alphabet_words, [arpepet_word]
        )
    )


def to_fandom_pronunciations(fandom, mappers):
    pages = list(find_generation_pages(
        f'{fandom}/wiki/Pokémon_Pronunciation_Guide'
    ))
    return {
        name.id: name for page in pages
        for name in parse_generation_page(page, mappers)
    }


def to_all_pronunciations(
        mappers, reviewers, mon_list,
        fandom_pronunciations
    ):
    return [
        fandom_pronunciations[mon.id]
        if mon.id in fandom_pronunciations else (
            mon_to_pronunciation(mappers, reviewers, mon)
        )
        for mon in mon_list
    ]
