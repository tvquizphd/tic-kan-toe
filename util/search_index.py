from pathlib import Path
from itertools import (
    product
)
from typing import (
    Dict, Callable
)
from sortedcontainers import SortedList
from pydantic import BaseSettings, BaseModel
from ipapy.arpabetmapper import ARPABETMapper
from recombinant import Learner
from g2p_en import G2p
from .base15 import (
    write_base15, read_base15
)
from .substitute import (
    to_substitute_dict_4grams
)
from .pronunciations import (
    find_pronunciations,
    mon_to_pronunciation
)
from .mappers import Mappers
from .search_results import (
    index_search_results#, unpack_results
)


INDEX = {
    k: Path('data') / v for k,v in
    {
        'INDEX': 'search-index',
        'MODEL_KEYS': 'search-model-keys.env.base15',
        'MODEL_VALS': 'search-model-vals.env.base15',
        '4_PHONES': 'search-fit-4-phones.env.base15'
    }.items()
}
INDEX['INDEX'].mkdir(parents=True, exist_ok=True)

class TrainedModel(BaseModel):
    placement: Dict[str, int]
    ranks: SortedList
    class Config:
        arbitrary_types_allowed = True

class Reviewers(BaseModel):
    rate_phonotactics: Callable[[str], int]

class Index(BaseSettings):
    pass


def with_only_alphabet(word):
    return "".join(
        x for x in word if x.isalpha()
    )


def to_alphabet_bigrams(word: str):
    x = with_only_alphabet(word.lower())
    return set(
        a+b for a,b in zip(x,x[1:])
    )


def read_model_placement_dict(arpepet_list):
    def read_keys():
        try:
            yield from read_base15(
                INDEX['MODEL_KEYS'], arpepet_list
            )
        except FileNotFoundError:
            pass
    def read_vals():
        try:
            yield from read_base15(INDEX['MODEL_VALS'])
        except FileNotFoundError:
            pass
    return dict(zip(read_keys(), read_vals()))


def read_model_ranks():
    try:
        return SortedList([0] + list(
            read_base15(INDEX['MODEL_VALS'])
        ))
    except FileNotFoundError:
        return SortedList([])


def write_fit_substitute_dict(
    file_name, substitute_dict, arpepet_list
    ):
    phones = [
        ' '.join([k,v]) for k,v
        in substitute_dict.items()
    ]
    write_base15(file_name, phones, arpepet_list)


def read_fit_substitute_dict(
    file_name, arpepet_list
    ):
    def read_fit_substitutes():
        all_pairs = list(read_base15(
            file_name, arpepet_list
        ))
        for pair in all_pairs:
            key_value = pair.split(' ')
            assert len(key_value) == 2
            yield tuple(key_value)
    try:
        return dict(read_fit_substitutes())
    except FileNotFoundError:
        return None


def to_mappers():
    alphabet_list = list(
        'abcdefghijklmnopqrstuvwxyz'
    )
    arpepet_list =  (
        'A E I O U Y T S R F H N P C'
    ).split(' ')
    return Mappers(
        alphabet_to_arpabet = G2p(),
        ipa_to_arpabet = (
            ARPABETMapper().map_unicode_string
        ),
        arpepet_list = arpepet_list,
        alphabet_list = alphabet_list,
        alphabet_ngram_lists = {
            n: [
                ''.join(ngram) for ngram in
                product(alphabet_list, repeat=n)
            ]
            for n in [2, 4]
        },
        arpepet_ngram_lists = {
            n: [
                ''.join(ngram) for ngram in
                product(arpepet_list, repeat=n)
            ]
            for n in [4]
        },
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


def to_search_index():
    mappers = to_mappers()
    bigrams = mappers.alphabet_ngram_lists[2]
    try:
        return read_search_index(
            bigrams
        )
    except FileNotFoundError:
        return None


def read_search_index(bigrams):
    search_index = {}
    for k0 in bigrams:
        packed_vals = read_base15(
            INDEX['INDEX'] / f'{k0}.base15'
        )
        search_index[k0] = {}
        for k1,packed in zip(bigrams, packed_vals):
            search_index[k1] = packed 
    return search_index


def verify_search_index(mappers):
    bigrams = mappers.alphabet_ngram_lists[2]
    try:
        read_search_index(bigrams)
    except FileNotFoundError:
        return False
    return True


def set_search_index(**kwargs):

    mon_list = [*kwargs['mon_list']]
    del kwargs['mon_list']
    mappers = to_mappers()
    trained = TrainedModel(
        ranks = read_model_ranks(),
        placement = read_model_placement_dict(
            mappers.arpepet_list
        )
    )
    print('Finding saved search index')
    if verify_search_index(mappers):
        print('Using saved search index')
        return
    print('Found no saved search index')
    print('Reading names (from Let\'s Play Wiki)')
    mon_id_pronunciations = find_pronunciations(
        'https://pokemonlp.fandom.com', mappers
    )
    # Use syllables, not words, for performance
    well_formed_model = Learner([
        phone for name in mon_id_pronunciations.values() 
        for phone in name.syllable_phones
    ])
    ranking = well_formed_model.ranking
    if len(trained.ranks) and len(trained.placement):
        ranking.placement = trained.placement
        ranking.ranks = trained.ranks
    else:
        print('Learning phonotactics (over two epochs)')
        well_formed_model.optimize()
    print('Using learned phonotactics')
    reviewers = Reviewers(
        rate_phonotactics = ranking.p
    )
    # Define mons that are missing
    todo = 1020
    pronunciations = [
        mon_id_pronunciations[mon.id]
        if mon.id in mon_id_pronunciations and mon.id < todo else (
            mon_to_pronunciation(mappers, reviewers, mon)
        )
        for mon in mon_list
    ]
    # Map phones that are missing
    substitute_dict_4grams = read_fit_substitute_dict(
        INDEX['4_PHONES'], mappers.arpepet_list
    )
    if substitute_dict_4grams is None:
        print('Finding substitutions (arpepet 4-grams)')
        substitute_dict_4grams = to_substitute_dict_4grams(
            mappers, reviewers, [
                phones for phones in ranking.placement
                if any(
                    phones in name.phones
                    for name in pronunciations
                )
            ]
        ) 
    print(
        'Using substitutions for',
        len(substitute_dict_4grams),
        'missing arpepet 4-grams'
    )
    print('Creating full search index')
    search_index = index_search_results(
        mappers, pronunciations,
        substitute_dict_4grams
    )
    # TODO: aggregate top-level bigram results 
    print('Saving search index!')
    for k0,v0 in search_index.items():
        out_file = INDEX['INDEX'] / f'{k0}.base15'
        write_base15(out_file, [
            v0.get(k1, 0)
            for k1 in mappers.alphabet_ngram_lists[2]
        ])

    # Save substitutes
    write_fit_substitute_dict(
        INDEX['4_PHONES'], substitute_dict_4grams,
        mappers.arpepet_list
    )
    # Phone strings, sorted by rating for readability
    model_place_keys = [
        key for _, key in sorted([
            (reviewers.rate_phonotactics(key), key)
            for key in ranking.placement
        ], reverse=True)
    ]
    # Save trained model
    write_base15(INDEX['MODEL_VALS'], [
        ranking.placement[key] for key in model_place_keys
    ])
    write_base15(INDEX['MODEL_KEYS'],
        model_place_keys, mappers.arpepet_list
    )
