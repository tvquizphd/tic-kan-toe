from typing import (
    List, Dict, Set, Tuple 
)
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pydantic import BaseModel
from .ngram import (
    to_alphabet_ngram_start,
    to_arpepet_ngram_start,
    to_all_alphabet_ngrams,
    to_alphabet_ngram,
    to_arpepet_ngram,
    Grams
)
from .bit_sums import (
    bitwise_or,
    to_one_hot_encoding_sum,
    check_if_sum_has_index,
    from_one_hot_encoding,
    sum_all_bit_sums
)
from .arpepet import (
    alphabet_to_arpepet 
)

Result = Tuple[int, int]


class Search(BaseModel):
    listed_search: List[int]
    narrow_search: int
    broad_search: int


class SearchIndex(BaseModel):
    searches: Dict[str, Search]
    id_list: List[int]


class PackedIndex(BaseModel):
    subsets: Dict[str, Set[int]]
    id_list: List[int]


def to_matcher(to_index, from_grams):
    def matcher(bit_sum, grams):
        parsed = from_grams(grams)
        return any(
            check_if_sum_has_index(
                bit_sum, to_index(ngram)
            )
            for ngram in parsed
        )
    return matcher


def to_full_list_matcher(
        pronunciations, to_index, from_grams, kind, n
    ):
    bit_sum = sum_all_bit_sums([
        name.bit_sums for name in pronunciations
    ], kind, n)
    matcher = to_matcher(to_index, from_grams)
    def full_list_matcher(grams):
        return matcher(bit_sum, grams)
    return full_list_matcher 


def to_result_finder(
        pronunciations, to_index, from_grams, kind, n
    ):
    matcher = to_matcher(
        to_index, from_grams
    )
    def result_finder(grams):
        return to_one_hot_encoding_sum((
            name.id for name in pronunciations if (
                matcher(name.bit_sums[kind][n], grams)
            )
        ))
    return result_finder


def to_packed_index(index: SearchIndex):
    return PackedIndex(
        id_list=index.id_list, subsets={
            key: from_one_hot_encoding(
                search.narrow_search or
                search.broad_search
            )
            for key, search in index.searches.items()
        }
    )


def name_to_result(name):
    return name.id, len(name.phones)


def to_specific_search(mappers, kind, n):
    from_grams = ({
        'alphabet': to_alphabet_ngram,
        'arpepet': to_arpepet_ngram
    })[kind]
    to_index = mappers.ngram_indexer(kind, n)
    return to_index, from_grams, kind, n


def to_results_finder(mappers, pronunciations, keys):
    result_finders = {
        (kind, n): to_result_finder(
            pronunciations, *to_specific_search(mappers, kind, n)
        )
        for (kind, n) in keys
    }
    full_list_matchers = {
        (kind, n): to_full_list_matcher(
            pronunciations, *to_specific_search(mappers, kind, n)
        )
        for (kind, n) in keys
    }
    def results_finder(threadpool_args):
        (
            kind, n, ngram, log
        ) = threadpool_args
        find_in_full_list = full_list_matchers[(kind, n)]
        found = find_in_full_list(
            Grams(**{ kind: ngram })
        )
        if not found:
            return ngram, 0
        log(ngram, ngram[0], kind, n)
        result_finder = result_finders[(kind, n)]
        return ngram, result_finder(
            Grams(**{ kind: ngram })
        )
    return results_finder


def to_lock_log():
    lock = Lock()
    last_log = tuple() 
    def log(value, *keys):
        nonlocal last_log
        if last_log == tuple(keys):
            return
        with lock:
            last_log = tuple(keys)
            print(f'{value}...', end=' ', flush=True)
    return log


def to_all_ngram_results(
        mappers, pronunciations, keys 
    ):
    results_finder = to_results_finder(
        mappers, pronunciations, keys
    )
    log = to_lock_log()
    all_ngram_results = {}
    for kind, n in keys:
        print(f'{kind} {n}-grams...')
        with ThreadPoolExecutor(mappers.n_threads) as threadpool:
            all_ngram_results[(kind, n)] = dict(
                threadpool.map(results_finder, [
                    (kind, n, ngram, log)
                    for ngram in mappers.ngram_lists[kind][n]
                ])
            )
        print()
    return all_ngram_results


def to_search_log(grams, search):
    return '('.join([
        '->'.join([grams.alphabet, grams.arpepet]),
        '/'.join([
            f'{matches.bit_count()}' for matches in
            [ search.narrow_search, search.broad_search ]
        ])
    ]) + ')'


def to_searcher(
        mappers, all_ngram_results, substitutes,
        sorted_ngram_keys, n_narrowest_keys
    ):
    ngram_parsers = {
        **{
            ('arpepet', n): to_arpepet_ngram_start(
                substitutes['arpepet'][n], n
            )
            for n in [3, 4]
        },
        **{
            ('alphabet', n): to_all_alphabet_ngrams(n)
            for n in [3, 4]
        },
        ('alphabet', 2): to_alphabet_ngram_start(2)
    }
    def searcher(threadpool_args):
        (alphabet_4gram, log) = threadpool_args
        bigrams = [
            alphabet_4gram[:2], alphabet_4gram[2:]
        ]
        grams = Grams(
            alphabet = alphabet_4gram,
            arpepet = ''.join(
                alphabet_to_arpepet(mappers, alphabet_4gram)
            )
        )
        listed_search = [
            bitwise_or(
                all_ngram_results[key][ngram]
                for ngram in ngram_parsers[key](grams)
            )
            for key in sorted_ngram_keys
        ]
        search = Search(
            listed_search = listed_search,
            broad_search = bitwise_or(listed_search),
            narrow_search = bitwise_or(
                listed_search[:n_narrowest_keys]
            )
        )
        if search.narrow_search > 0:
            log(to_search_log(grams, search), bigrams[0])
        return bigrams, search
    return searcher


def count_results(ids, results):
    return {
        id: len([
            None for result in results
            if check_if_sum_has_index(result, id)
        ])
        for id in ids
    }


def sortSearchResults(searches, pronunciations, search_range):
    '''Sort from specific to generic
    '''
    mon_ids_to_length = {
        name.id: len(name.phones) for name in pronunciations
    }
    broad_sum = bitwise_or([
        search.broad_search for search in searches
    ])
    broad_ids = [
        name.id for name in pronunciations
        if check_if_sum_has_index(broad_sum, name.id)
    ]
    counts = [
        count_results(broad_ids, [
            search.listed_search[i] for search in searches
        ])
        for i in search_range
    ]
    total = len(searches)
    return [
        measured[-1] for measured in sorted([
            tuple(
                (total - count[id]) for count in counts
            ) + (
                mon_ids_to_length[id], id
            )
            for id in broad_ids
        ], reverse=True)
    ]


def index_search_results(
        mappers, all_ngram_results, substitutes,
        pronunciations, sorted_ngram_keys, n_narrowest_keys
    ):
    """Finds matching pronunciations for all 456,976
    combinations of four latin alphabet letters. The
    pronunciations match for any of the following:
        - initial two letters match
        - final three letters match
        - initial arpepet 3-gram matches
        - any arpepet 4-gram matches
    """
    search_range = list(range(len(sorted_ngram_keys)))
    searcher = to_searcher(
        mappers, all_ngram_results, substitutes,
        sorted_ngram_keys, n_narrowest_keys
    )
    indices = {
        bigram: SearchIndex(searches={}, id_list=[])
        for bigram in mappers.ngram_lists['alphabet'][2]
    }
    log = to_lock_log()
    with ThreadPoolExecutor(mappers.n_threads) as threadpool:
        searches = threadpool.map(searcher, [
            (alphabet_4gram, log) for alphabet_4gram 
            in mappers.ngram_lists['alphabet'][4]
        ])
        # Merge search results
        for keys, search in searches:
            indices[keys[0]].searches[keys[1]] = search
        # Sort search results
        for index in indices.values():
            searches = index.searches.values()
            index.id_list = sortSearchResults(
                searches, pronunciations, search_range
            )
    print('\nFound search results.')
    return {
        k0: to_packed_index(v0)
        for k0,v0 in indices.items()
    }
