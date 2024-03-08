import re
import csv
import math
from pathlib import Path
from itertools import accumulate
from typing import Dict, List, Callable
from pydantic import BaseSettings, BaseModel
from ipapy.arpabetmapper import ARPABETMapper
from recombinant import Learner
import wikitextparser as wtp
from g2p_en import G2p
from .base15 import write_base15, read_base15
from . import get_api


INDEX = {
    k: Path('data') / v for k,v in
    ({
        'MODEL_RANKS': 'search-model-ranks.env.base15',
        'MODEL_PLACE_KEYS': 'search-model-placement-keys.env.csv',
        'MODEL_PLACE_VALS': 'search-model-placement-vals.env.base15'
    }).items()
}

class TrainedModel(BaseModel):
    placement: Dict[str, int]
    ranks: List[int]

class Mappers(BaseModel):
    ipa_to_arpabet: Callable[[str], List[str]]
    alpha_to_arpabet: Callable[[str], List[str]]

class Reviewers(BaseModel):
    rate_phonotactics: Callable[[str], int]

class Pronunciation(BaseModel):
    id: int
    ipa: str
    arpepet: List[List[str]]

class Index(BaseSettings):
    pass

def arpabet_to_arpepet(arpa_list):
    converter = {
        arpa_key: arpe_key 
        for arpe_key, arpa_str in ({
            'A': 'AA AO AH',
            'E': 'AE AX EH ER',
            'I': 'IH IY iX Y',
            'O': 'AW OW',
            'U': 'UH UW UX W WH',
            'Y': 'AY EY OY',
            'T': 'T D',
            'S': 'S SH Z ZH',
            'R': 'L R EL DX AXR',
            'F': 'DH TH F V',
            'H': 'G K HH Q',
            'N': 'M N NG NX EM EN',
            'P': 'B P',
            'C': 'CH JH'
        }).items()
        for arpa_key in arpa_str.split(' ')
    }
    for arpa_phone in arpa_list:
        arpa = "".join(
            x for x in arpa_phone if x.isalpha()
        )
        # Handle non-standard arpabet
        if arpa not in converter:
            yield from ({
                'EA': ['E', 'R'],
                'IA': ['I', 'R']
            }).get(arpa, list(arpa))
            continue
        yield converter[arpa]

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
        parse_page_item(mappers, t.arguments)
        for t in wtp.parse(page_text).templates
        if len(t.arguments) in { 7, 8 }
    ]

def evaluate_break(phones, word_breaks, index, pre, post):
    post_zip = list(zip(phones[index:], post))
    pre_zip = list(
        zip(phones[:index][::-1], pre[::-1])
    )[::-1]
    same_first_post = len(post_zip) > 0 and (
        1 == len(set(post_zip[0]))
    )
    # Prioritize word-break, then post, then pre
    at_word_break = len(word_breaks) >= 1 and 0 == min([
        abs(index - space) for space in word_breaks
    ]) 
    return (
        int(at_word_break),
        int(same_first_post),
        sum(word_c == c for word_c, c in post_zip),
        sum(word_c == c for word_c, c in pre_zip)
    )


def find_syllable_breaks(word_breaks, syllables, phones):
    min_syllable_phones = 2
    break_start = 0
    break_index = 0
    index_sum = sum(
        len(syllable) for syllable in syllables
    )
    for pre, post in zip(
        syllables[:-1], syllables[1:]
    ):
        # Convert input to output index
        break_index += len(pre)
        break_choices = []
        starts = set(word_breaks + [
            nearest(len(phones) * (
                break_index / index_sum
            ))
            for nearest in [math.floor, math.ceil]
        ])
        for start in starts:
            smallest_margin = min(
                start, len(phones) - start,
                start - break_start
            )
            if smallest_margin < min_syllable_phones:
                continue
            break_choices.append(evaluate_break(
                phones, word_breaks, start, pre, post 
            ) + (start,))
        if len(break_choices) < 1:
            break_start = round(len(phones) * (
                break_index / index_sum
            ))
            continue
        choice = sorted(
            break_choices, reverse=True
        )[0]
        break_start = choice[-1]
        yield choice


def match_syllables(syllables, words):
    phones = [
        phone for word in words 
        for phone in word
    ]
    word_breaks = list(accumulate([
        len(word) for word in words
    ]))[:-1]
    # 1 to 7: 1 break, 8 to 11: 2 breaks
    n_breaks_out = max(1,len(phones) // 4)
    best_breaks = sorted(
        find_syllable_breaks(
            word_breaks, syllables, phones
        ),
        reverse=True
    )
    if len(best_breaks) == 0:
        return [ phones ]
    starts = sorted([
        x[-1] for x in best_breaks
    ][:n_breaks_out])
    return [
        phones[slice(*pair)] for pair in zip(
            [0] + starts, starts + [None]
        )
    ]


def parse_page_item(mappers, args):
    respelled_syllables = args[5].value.lower().split('-')
    arpepet_of_eng_syllables = [
        list(arpabet_to_arpepet(
            mappers.alpha_to_arpabet(syllable)
        ))
        for syllable in respelled_syllables
    ]
    arpepet_of_ipa_words = [
        list(arpabet_to_arpepet(
            mappers.ipa_to_arpabet(
                ipa_word, ignore=True, return_as_list=True
            )
        ))
        for ipa_word in args[6].value.split(' ')
    ]
    arpepet = match_syllables(
        arpepet_of_eng_syllables,
        arpepet_of_ipa_words,
    )
    return Pronunciation(
        id=int(args[0].value),
        ipa=args[6].value,
        arpepet=arpepet
    )

def get_raw(guide, url):
    return get_api(guide, f'{url}?action=raw', 'text')


def read_model_placement_dict():
    def read_keys():
        try:
            with open(INDEX['MODEL_PLACE_KEYS'], 'r', encoding='utf-8') as f:
                place_reader = csv.reader(f, delimiter=',')
                yield from [x for row in place_reader for x in row]
        except FileNotFoundError:
            pass
    def read_vals():
        try:
            yield from read_base15(INDEX['MODEL_PLACE_VALS'])
        except FileNotFoundError:
            pass

    return dict(zip(read_keys(), read_vals()))


def read_model_ranks():
    try:
        yield from read_base15(INDEX['MODEL_RANKS'])
    except FileNotFoundError:
        pass

def to_search_index():
    model_ranks = list(read_model_ranks())
    model_placement = read_model_placement_dict()


def set_search_index(**kwargs):

    trained = TrainedModel(
        ranks = list(read_model_ranks()),
        placement = read_model_placement_dict()
    )
    is_trained = all((
        len(trained.ranks), len(trained.placement)
    ))
    mon_list = [*kwargs['mon_list']]
    del kwargs['mon_list']
    mappers = Mappers(
        alpha_to_arpabet = G2p(),
        ipa_to_arpabet = (
            ARPABETMapper().map_unicode_string
        )
    )
    fandom = 'https://pokemonlp.fandom.com'
    print('Reading pronunciations (from Let\'s Play Wiki)')
    pages = list(find_generation_pages(
        f'{fandom}/wiki/Pokémon_Pronunciation_Guide'
    ))
    pronunciations = [
        name for page in pages
        for name in parse_generation_page(
            page, mappers
        )
    ]
    # Use syllables, not words, for performance
    valid_arpepet = [
        ''.join(syllable)
        for name in pronunciations
        for syllable in name.arpepet
    ]
    well_formed_model = Learner(valid_arpepet)
    ranking = well_formed_model.ranking
    if is_trained:
        ranking.ranks = trained.ranks
        ranking.placement = trained.placement
        print('Loaded learned phonotactics')
    else:
        print('Learning phonotactics (over two epochs)')
        well_formed_model.optimize()
    reviewers = Reviewers(
        rate_phonotactics = ranking.p
    )
    # Save trained model
    placement = ranking.placement
    ranks = ranking.ranks

    # Test
    print(
        reviewers.rate_phonotactics('PICU'),
        reviewers.rate_phonotactics('PIHA'),
        reviewers.rate_phonotactics('PIHAPI')
    )

    write_base15(INDEX['MODEL_RANKS'], ranks)

    model_place_keys = sorted(placement.keys())

    with open(INDEX['MODEL_PLACE_KEYS'], 'w', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(model_place_keys)

    write_base15(INDEX['MODEL_PLACE_VALS'], [
        placement[key] for key in model_place_keys
    ])

    print('pronunciations')
