from pathlib import Path
from typing import (
    Dict, Callable
)
from sortedcontainers import SortedList
from pydantic import BaseModel
from recombinant import Learner
from .mappers import (
    Mappers, to_mappers 
)
from .ngram import to_ngram_set
from .base15 import (
    write_base15, read_base15
)
from .bit_sums import (
    to_one_hot_encoding_sum,
    from_one_hot_encoding
)
from .substitute import (
    to_ngram_substitutes
)
from .pronunciations import (
    to_fandom_pronunciations,
    to_all_pronunciations
)
from .search_results import (
    PackedIndex,
    index_search_results,
    to_all_ngram_results
)

VERSION = "v1.2.0"
INDEX = {
    k: Path('data') / v for k,v in
    {
        'NGRAMS': 'search-ngrams',
        'INDEX': f'search-index-{VERSION}',
        'SUBSETS': f'search-subsets-{VERSION}',
        'MODEL_KEYS': 'search-model-keys.env.base15',
        'MODEL_VALS': 'search-model-vals.env.base15',
        '2_PHONES': 'search-fit-2-phones.env.base15',
        '3_PHONES': 'search-fit-3-phones.env.base15',
        '4_PHONES': 'search-fit-4-phones.env.base15'
    }.items()
}
for directory in ['NGRAMS', 'SUBSETS', 'INDEX']:
    INDEX[directory].mkdir(parents=True, exist_ok=True)

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


def verify_packed_index(mappers, mon_list):
    bigrams = mappers.ngram_lists['alphabet'][2]
    try:
        packed = {
            first: read_one_packed_index(bigrams, first)
            for first in (bigrams[0], bigrams[-1])
        }
        for first, last in zip('az', 'za'):
            print(
                f'Results for "{first*2}{last*2}":',
                ', '.join(list(
                mon_list[id-1].name
                for id in packed[first*2].id_list
                if id in packed[first*2].subsets[last*2]
            )))
    except FileNotFoundError:
        return False
    return True


def read_one_ngram_result(mappers, kind, n):
    path = INDEX['NGRAMS'] / f'{kind}-{n}.env.base15'
    ngram_list = mappers.ngram_lists[kind][n]
    try:
        return dict(zip(
            ngram_list, read_base15(path)
        ))
    except FileNotFoundError:
        return None


def read_all_ngram_results(mappers, sorted_ngram_keys):
    results = {
        key: read_one_ngram_result(mappers, *key)
        for key in sorted_ngram_keys
    }
    return {
        k: v for k,v in results.items() if v
    }


def save_one_ngram_result(mappers, kind, n, result):
    path = INDEX['NGRAMS'] / f'{kind}-{n}.env.base15'
    ngram_list = mappers.ngram_lists[kind][n]
    write_base15(
        path, [result[ngram] for ngram in ngram_list]
    )

def save_all_ngram_results(mappers, all_ngram_results):
    for (kind, n), result in all_ngram_results.items():
        save_one_ngram_result(mappers, kind, n, result)


def read_one_packed_index(bigrams, bigram):
    id_list = list(read_base15(
        INDEX['INDEX'] / f'{bigram}.env.base15'
    ))
    encodings = read_base15(
        INDEX['SUBSETS'] / f'{bigram}.env.base15'
    )
    subsets = {
        key: set(
            id_list[bit] for bit in 
            from_one_hot_encoding(encoding)
        )
        for key, encoding in zip(bigrams, encodings)
    }
    return PackedIndex(
        id_list=id_list, subsets=subsets
    )


def save_one_packed_index(bigrams, bigram, packed_index):
    index_list_path = INDEX['INDEX'] / f'{bigram}.env.base15'
    subset_path = INDEX['SUBSETS'] / f'{bigram}.env.base15'
    write_base15(index_list_path, packed_index.id_list)
    write_base15(subset_path, [
        to_one_hot_encoding_sum(
            packed_index.id_list.index(id)
            for id in packed_index.subsets[key]
        )
        for key in bigrams
    ])


def save_packed_index_results(
        mappers: Mappers,
        packed_index_results: Dict[str,PackedIndex]
    ):
    bigrams = mappers.ngram_lists['alphabet'][2]
    for bigram, packed_index in packed_index_results.items():
        save_one_packed_index(bigrams, bigram, packed_index)


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
                mappers, reviewers, ranking.placement, n
            ) 
    return substitutes 


def set_packed_index(**kwargs):

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
    if verify_packed_index(mappers, mon_list):
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
        len(substitutes['arpepet'][4]), '4-grams'
    )
    sorted_ngram_keys = [
        (kind, n)
        for n in (4, 3)
        for kind in ('alphabet', 'arpepet')
    ]
    print(
        'Finding results for:', ', '.join([
            f'{kind} {n}-grams' for kind, n in sorted_ngram_keys
        ]), '...'
    )
    ngram_results = read_all_ngram_results(
        mappers, sorted_ngram_keys
    )
    all_ngram_results = {
        **ngram_results, **to_all_ngram_results(
            mappers, pronunciations,
            [
                key for key in sorted_ngram_keys 
                if key not in ngram_results
            ]
        )
    }
    print('\nFound n-gram results.')
    print('Creating full search index (from aaaa to zzzz)...')
    packed_index_results = index_search_results(
        mappers, all_ngram_results, substitutes,
        pronunciations, sorted_ngram_keys 
    )
    save_all_ngram_results(mappers, all_ngram_results)
    save_arpepet_substitutes(mappers, substitutes)
    save_packed_index_results(
        mappers, packed_index_results
    )
    save_model(mappers, reviewers, ranking)
    print('Saved!')
