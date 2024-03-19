from typing import (
    List, Dict, Set, Tuple 
)
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pydantic import BaseModel
from .ngram import (
    to_alphabet_bigram_start,
    to_alphabet_trigram_end,
    to_all_arpepet_ngram_start,
    to_all_arpepet_ngrams,
    to_alphabet_ngram,
    to_arpepet_ngram,
    Grams
)
from .bit_sums import (
    bitwise_or, bitwise_and,
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
    broad_results: int
    narrow_results: int
    precise_results: int


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
            key: from_one_hot_encoding(search.broad_results)
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
    n_threads = mappers.n_threads
    all_ngram_results = {}
    for kind, n in keys:
        print(f'{kind} {n}-grams...')
        with ThreadPoolExecutor(n_threads) as threadpool:
            all_ngram_results[(kind, n)] = dict(
                threadpool.map(results_finder, [
                    (kind, n, ngram, log)
                    for ngram in mappers.ngram_lists[kind][n]
                ])
            )
        print()
    return all_ngram_results


def format_searching_log(grams, searching):
    return '('.join([
        '->'.join([grams.alphabet, grams.arpepet]),
        '/'.join([
            f'{matches.bit_count()}' for matches in
            sorted(set(searching))
        ])
    ]) + ')'


def to_searcher(
        mappers, all_ngram_results, checklist,
        most_precise_keys
    ):
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
        searching = [None, None, None]
        precise_key = len(searching) - 1
        comparisons = [bitwise_or, bitwise_or, bitwise_and]
        for (kind, n), from_grams in checklist.items():
            results = bitwise_or(
                all_ngram_results[(kind, n)][ngram]
                for ngram in from_grams(grams)
            )
            for i,fn in enumerate(comparisons):
                if i == 0 or (kind, n) in most_precise_keys:
                    if searching[i] != None:
                        searching[i] = fn([searching[i], results])
                    else:
                        searching[i] = results
        if searching[precise_key] > 0:
            log(format_searching_log(grams, searching), bigrams[0])
        return bigrams, Search(
            precise_results=searching[2],
            narrow_results=searching[1],
            broad_results=searching[0]
        )
    return searcher


def count_results(ids, results):
    return {
        id: len([
            None for result in results
            if check_if_sum_has_index(result, id)
        ])
        for id in ids
    }


def sortSearchResults(searches, pronunciations):
    '''Sort from specific to generic
    '''
    mon_ids_to_length = {
        name.id: len(name.phones) for name in pronunciations
    }
    broad_sum = bitwise_or([
        search.broad_results for search in searches
    ])
    broad_ids = [
        name.id for name in pronunciations
        if check_if_sum_has_index(broad_sum, name.id)
    ]
    broad_counts = count_results(broad_ids, [
        search.broad_results for search in searches
    ])
    narrow_counts = count_results(broad_ids, [
        search.narrow_results for search in searches
    ])
    precise_counts = count_results(broad_ids, [
        search.precise_results for search in searches
    ])
    total = len(searches)
    return [
        measured[-1] for measured in sorted([
            (
                total - broad_counts[id],
                total - narrow_counts[id],
                total - precise_counts[id],
                mon_ids_to_length[id], id
            )
            for id in broad_ids
        ], reverse=True)
    ]


def index_search_results(
        mappers, all_ngram_results, substitutes,
        pronunciations, most_precise_keys
    ):
    """Finds matching pronunciations for all 456,976
    combinations of four latin alphabet letters. The
    pronunciations match for any of the following:
        - initial two letters match
        - final three letters match
        - initial arpepet 3-gram matches
        - any arpepet 4-gram matches
    """
    checklist = {
        k:v for k,v in ({
            ('alphabet', 2): to_alphabet_bigram_start,
            ('alphabet', 3): to_alphabet_trigram_end,
            ('arpepet', 3): to_all_arpepet_ngram_start(
                substitutes['arpepet'][3], 3
            ),
            ('arpepet', 4): to_all_arpepet_ngrams(
                substitutes['arpepet'][4], 4
            )
        }).items()
        if k in all_ngram_results
    }
    searcher = to_searcher(
        mappers, all_ngram_results, checklist,
        most_precise_keys
    )
    indices = {
        bigram: SearchIndex(searches={}, id_list=[])
        for bigram in mappers.ngram_lists['alphabet'][2]
    }
    log = to_lock_log()
    n_threads = mappers.n_threads
    with ThreadPoolExecutor(n_threads) as threadpool:
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
                searches, pronunciations
            )
    print('\nFound search results.')
    return {
        k0: to_packed_index(v0)
        for k0,v0 in indices.items()
    }
