import re
import csv
import math
from pathlib import Path
from itertools import (
    accumulate, product, chain 
)
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
        '2_PHONES': 'search-fit-replacement-2-phones.env.base15',
        '3_PHONES': 'search-fit-replacement-3-phones.env.base15',
        '4_PHONES': 'search-fit-replacement-4-phones.env.base15',
        'MODEL_PLACE_KEYS': 'search-model-placement-keys.env.csv',
        'MODEL_PLACE_VALS': 'search-model-placement-vals.env.base15'
    }).items()
}

# Python 3.12 has itertools.batched
def batched(inputs, n):
    for i in range(0, len(inputs), n):
        yield inputs[i:i + n]

class TrainedModel(BaseModel):
    placement: Dict[str, int]
    ranks: List[int]

class Mappers(BaseModel):
    arpepet_table: Dict[str, str]
    arpepet_vowels: List[List[str]]
    arpepet_consonants: List[List[str]]
    ipa_to_arpabet: Callable[[str], List[str]]
    alpha_to_arpabet: Callable[[str], List[str]]

class Reviewers(BaseModel):
    rate_phonotactics: Callable[[str], int]

class Pronunciation(BaseModel):
    id: int
    syllable_phones: List[str]
    phones: str

class Index(BaseSettings):
    pass

def arpabet_to_arpepet(arpepet_table, arpa_list):
    converter = {
        arpa_key: arpe_key 
        for arpe_key, arpa_str in (arpepet_table).items()
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

def evaluate_break(phone_list, word_breaks, index, pre, post):
    post_zip = list(zip(phone_list[index:], post))
    pre_zip = list(
        zip(phone_list[:index][::-1], pre[::-1])
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


def find_syllable_breaks(word_breaks, syllables, phone_list):
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
            nearest(len(phone_list) * (
                break_index / index_sum
            ))
            for nearest in [math.floor, math.ceil]
        ])
        for start in starts:
            smallest_margin = min(
                start, len(phone_list) - start,
                start - break_start
            )
            if smallest_margin < min_syllable_phones:
                continue
            break_choices.append(evaluate_break(
                phone_list, word_breaks, start, pre, post 
            ) + (start,))
        if len(break_choices) < 1:
            break_start = round(len(phone_list) * (
                break_index / index_sum
            ))
            continue
        choice = sorted(
            break_choices, reverse=True
        )[0]
        break_start = choice[-1]
        yield choice


def match_syllables(syllables, words):
    phone_list = [
        phone for word in words 
        for phone in word
    ]
    word_breaks = list(accumulate([
        len(word) for word in words
    ]))[:-1]
    # 1 to 7: 1 break, 8 to 11: 2 breaks
    n_breaks_out = max(1,len(phone_list) // 4)
    best_breaks = sorted(
        find_syllable_breaks(
            word_breaks, syllables, phone_list
        ),
        reverse=True
    )
    if len(best_breaks) == 0:
        return [ ''.join(phone_list) ]
    starts = sorted([
        x[-1] for x in best_breaks
    ][:n_breaks_out])
    return [
        ''.join(phone_list[slice(*pair)]) for pair in zip(
            [0] + starts, starts + [None]
        )
    ]


def parse_page_item(mappers, args):
    respelled_syllables = args[5].value.lower().split('-')
    arpepet_of_eng_syllables = [
        list(arpabet_to_arpepet(
            mappers.arpepet_table,
            mappers.alpha_to_arpabet(syllable)
        ))
        for syllable in respelled_syllables
    ]
    arpepet_of_ipa_words = [
        list(arpabet_to_arpepet(
            mappers.arpepet_table,
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
        syllable_phones=arpepet,
        phones=''.join(arpepet)
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


def to_arpepet_variant(
    arpepet_vowels, arpepet_consonants, phone
    ):
    phone_matrix, idx1, idx2 = (None, None, None)
    for matrix in (arpepet_vowels, arpepet_consonants):
        vector = [value for row in matrix for value in row]
        width = len(matrix[0])
        try:
            flat_idx = vector.index(phone)
            idx1, idx2 = divmod(flat_idx, width)
            phone_matrix = matrix
            break
        except ValueError:
            pass
    if phone_matrix is None:
        return []
    # Options
    return set(
        value
        for i1,row in enumerate(phone_matrix)
        for i2,value in enumerate(row)
        if (idx2 == i2 or idx1 == i1)
        and value != phone
    )

def to_arpepet_variants(
    arpepet_vowels, arpepet_consonants,
    rate_phonotactics, phones
    ):
    vowels = [
        v for row in arpepet_vowels for v in row
    ]
    variants = []
    for index, phone_in in enumerate(list(phones)):
        for phone_out in to_arpepet_variant(
            arpepet_vowels, arpepet_consonants, phone_in 
        ):
            phones_out = ''.join([
                phone_out if i == index else x
                for i,x in enumerate(list(phones))
            ])
            variants.append((
                int(phone_in not in vowels), 
                rate_phonotactics(phones_out),
                phones_out   
            ))
    return [v[-1] for v in sorted(variants, reverse=False)]


def handle_missing_phones(
    mappers, reviewers, valid_phones,
    replacement_dict, n
    ):
    arpepet_consonants = mappers.arpepet_consonants
    arpepet_vowels = mappers.arpepet_vowels
    missing_phones = [
        ''.join(chain(args)) for args in product(
            mappers.arpepet_table.keys(), repeat=n
        )
        if ''.join(chain(args)) not in valid_phones 
    ]
    for missing_phone in missing_phones:
        for args in replacement_dict.items():
            replaced = missing_phone.replace(*args)
            if replaced in valid_phones:
                yield missing_phone, replaced
                continue

        variants = to_arpepet_variants(
            mappers.arpepet_vowels,
            mappers.arpepet_consonants,
            reviewers.rate_phonotactics,
            missing_phone
        )
        for variant in variants:
            if variant in valid_phones:
                yield missing_phone, variant
                break


def save_replacement_dict(
    file_name, replacement_dict,
    sorted_arpepet_phones, n
    ):
    def serialize_replacement(k,v):
        assert len(k) == n and len(v) == n
        return [
            sorted_arpepet_phones.index(phone)
            for phone in list(k+v)
        ]
    write_base15(file_name, [
        i for k,v in replacement_dict.items()
        for i in serialize_replacement(k,v)
    ])


def load_replacement_dict(
    file_name, sorted_arpepet_phones, n
    ):
    def load_replacements():
        all_indices = list(read_base15(file_name))
        for indices in batched(all_indices, 2*n):
            if len(indices) != 2*n:
                continue
            yield tuple(
                ''.join([
                    sorted_arpepet_phones[i] for i in chunk
                ])
                for chunk in (indices[:n], indices[n:])
            )
    try:
        return dict(load_replacements())
    except FileNotFoundError:
        return None

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
        ),
        arpepet_table = {
            'A': 'AA AO AH',
            'E': 'AE AX EH ER',
            'I': 'IH IY IX',
            'O': 'AW OW',
            'U': 'UH UW UX W WH',
            'Y': 'AY EY OY Y',
            'T': 'T D',
            'S': 'S SH Z ZH',
            'R': 'L R EL DX AXR',
            'F': 'DH TH F V',
            'H': 'G K HH Q',
            'N': 'M N NG NX EM EN',
            'P': 'B P',
            'C': 'CH JH'
        },
        arpepet_vowels = [
            ['Y','U'],
            ['I','O'],
            ['E','A'],
        ],
        arpepet_consonants = [
            ['P', 'T', 'H', 'N'],
            ['F', 'S', 'C', 'R']
        ]
    )
    sorted_arpepet_phones = sorted(
        mappers.arpepet_table.keys()
    )
    replacement_dicts = {
        n: load_replacement_dict(
            INDEX[f'{n}_PHONES'], sorted_arpepet_phones, n=n
        )
        for n in [ 2, 3, 4 ]
    }
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
    well_formed_model = Learner([
        phone for name in pronunciations
        for phone in name.syllable_phones
    ])
    ranking = well_formed_model.ranking
    if is_trained:
        ranking.ranks = trained.ranks
        ranking.placement = trained.placement
        print('Loaded learned phonotactics')
    else:
        print('Learning phonotactics (over two epochs)')
        well_formed_model.optimize()
    valid_phones = [
        phones for phones in ranking.placement
        if any(
            phones in name.phones
            for name in pronunciations
        )
    ]
    print(
        f'{len(valid_phones)}/{len(pronunciations)}',
        'phone sequences in model were found in name list'
    )
    reviewers = Reviewers(
        rate_phonotactics = ranking.p
    )
    # Construct directory structure
    print('Constructing search index (for 2-4 phones)')
    four_phones = [
        phones
        for phones in valid_phones if len(phones) == 4
    ]
    three_phones = {
        phones: [
            four_phone for four_phone in four_phones
            if phones in four_phone
        ]
        for phones in valid_phones if len(phones) == 3
    }
    two_phones = {
        phones: {
            three_phone: four_phones_list
            for three_phone, four_phones_list
            in three_phones.items() if phones in three_phone
        }
        for phones in valid_phones 
        if len(phones) == 2
    }
    # Map phones that are missing 
    replacement_two_phones = replacement_dicts[2]
    if  replacement_dicts[2] is None:
        replacement_dicts[2] = dict(handle_missing_phones(
            mappers, reviewers, list(two_phones.keys()), {}, n=2
        ))
    print('two-phone replacements:', len(replacement_dicts[2]), 'chosen')
    replacement_three_phones = replacement_dicts[3]
    if  replacement_dicts[3] is None:
        replacement_dicts[3] = dict(handle_missing_phones(
            mappers, reviewers, list(three_phones.keys()),
            replacement_dicts[2], n=3
        ))
    print('three-phone replacements:', len(replacement_dicts[3]), 'chosen')
    if  replacement_dicts[4] is None:
        replacement_dicts[4] = dict(handle_missing_phones(
            mappers, reviewers, four_phones,
            replacement_dicts[2], n=4
        ))
    print('four-phone replacements:', len(replacement_dicts[4]), 'chosen')

    print('Saving search index!')
    # Save replacements of all lengths
    for n, replacement_dict in replacement_dicts.items():
        save_replacement_dict(
            INDEX[f'{n}_PHONES'], replacement_dict,
            sorted_arpepet_phones, n=n
        )
    # Save trained model
    write_base15(INDEX['MODEL_RANKS'], ranking.ranks)
    # Phone strings, sorted by rating for readability
    model_place_keys = [
        key for _, key in sorted([
            (reviewers.rate_phonotactics(key), key)
            for key in ranking.placement
        ], reverse=True)
    ]
    write_base15(INDEX['MODEL_PLACE_VALS'], [
        ranking.placement[key] for key in model_place_keys
    ])
    with open(INDEX['MODEL_PLACE_KEYS'], 'w', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter=',')
        writer.writerow(model_place_keys)
