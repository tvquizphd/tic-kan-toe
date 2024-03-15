from pathlib import Path
from typing import (
    Dict, Callable
)
from sortedcontainers import SortedList
from pydantic import BaseModel
from recombinant import Learner
from .mappers import to_mappers 
from .ngram import to_ngram_set
from .base15 import (
    write_base15, read_base15
)
from .substitute import (
    to_ngram_substitutes
)
from .pronunciations import (
    to_fandom_pronunciations,
    to_all_pronunciations
)
from .search_results import (
    index_search_results#, unpack_results
)


INDEX = {
    k: Path('data') / v for k,v in
    {
        'INDEX': 'search-index',
        'MODEL_KEYS': 'search-model-keys.env.base15',
        'MODEL_VALS': 'search-model-vals.env.base15',
        '2_PHONES': 'search-fit-2-phones.env.base15',
        '3_PHONES': 'search-fit-3-phones.env.base15',
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


def with_only_alphabet(word):
    return "".join(
        x for x in word if x.isalpha()
    )

def to_alphabet_bigrams(word: str):
    x = with_only_alphabet(word.lower())
    return to_ngram_set(x, 2)


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


def to_search_index():
    mappers = to_mappers()
    bigrams = mappers.ngram_lists['alphabet'][2]
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
    bigrams = mappers.ngram_lists['alphabet'][2]
    try:
        read_search_index(bigrams)
    except FileNotFoundError:
        return False
    return True


def save_search_index(mappers, search_index):
    for k0,v0 in search_index.items():
        out_file = INDEX['INDEX'] / f'{k0}.base15'
        write_base15(out_file, [
            v0.get(k1, 0)
            for k1 in mappers.ngram_lists['alphabet'][2]
        ])


def save_arpepet_substitutes(mappers, substitutes):
    for n, subs in substitutes['arpepet'].items():
        write_fit_substitute_dict(
            INDEX[f'{n}_PHONES'], subs, mappers.arpepet_list
        )


def save_model(mappers, reviewers, ranking):
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


def load_arpepet_substitutes(
        n_list, mappers, reviewers, ranking 
    ):
    substitutes = {
        n: read_fit_substitute_dict(
            INDEX[f'{n}_PHONES'], mappers.arpepet_list
        )
        for n in n_list 
    }
    for n in n_list:
        if substitutes[n] is None:
            substitutes[n] = to_ngram_substitutes(
                n, mappers, reviewers, ranking.placement
            ) 
    return substitutes 


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
    print(
        'Found no saved search index',
        '\nReading names (from Fandom Wiki)...'
    )
    fandom_pronunciations = to_fandom_pronunciations(
        'https://pokemonlp.fandom.com', mappers
    )
    print('Read names. Finding phonotactics...')
    # Use syllables to learn phonotactics
    well_formed_model = Learner([
        phone for name in fandom_pronunciations.values() 
        for phone in name.syllable_phones
    ])
    ranking = well_formed_model.ranking
    if len(trained.ranks) and len(trained.placement):
        ranking.placement = trained.placement
        ranking.ranks = trained.ranks
        print('Found phonotactics.')
    else:
        print('Learning phonotactics (over two epochs)...')
        well_formed_model.optimize()
        print('Learned phonotactics.')
    reviewers = Reviewers(rate_phonotactics = ranking.p)
    # Find pronunciations for any missing mons
    pronunciations = to_all_pronunciations(
        mappers, reviewers, mon_list,
        fandom_pronunciations
    ) 
    print('Finding substitutes...')
    # Map phones that are missing
    substitutes = {
        'arpepet': load_arpepet_substitutes(
            [2, 3, 4], mappers, reviewers, ranking
        ) 
    }
    print(
        'Substitutes for arpepet:',
        len(substitutes['arpepet'][2]), '2-grams,',
        len(substitutes['arpepet'][3]), '3-grams, and',
        len(substitutes['arpepet'][4]), '4-grams',
        '\nCreating full search index (from aaaa to zzzz)'
    )
    search_index = index_search_results(
        mappers, pronunciations, substitutes
    )
    # TODO: aggregate top-level bigram results 
    save_arpepet_substitutes(mappers, substitutes)
    save_search_index(mappers, search_index)
    save_model(mappers, reviewers, ranking)
    # Phone strings, sorted by rating for readability
    print('Saved!')
