from typing import (
    Dict, Set, Tuple 
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
    to_ngram_set,
    Grams
)
from .bit_sums import (
    to_one_hot_encoding_sum,
    from_one_hot_encoding_sum,
    check_if_sum_has_index,
    sum_all_bit_sums
)
from .arpepet import (
    alphabet_to_arpepet 
)

Result = Tuple[int, int, int, int, int, int]

class Search(BaseModel):
    results: Set[Result]
    tail: Dict[str, 'Search']
Search.update_forward_refs()


def name_to_result(name):
    return (
        name.id,
        name.bit_sums['alphabet'][2],
        name.bit_sums['alphabet'][3],
        name.bit_sums['arpepet'][2],
        name.bit_sums['arpepet'][3],
        name.bit_sums['arpepet'][4]
    )


def to_ngram_checker(to_index, from_grams):
    def ngram_checker(bit_sum, grams):
        parsed = from_grams(grams)
        return any(
            check_if_sum_has_index(
                bit_sum, to_index(ngram)
            )
            for ngram in parsed
        )
    return ngram_checker 


def to_full_list_matcher(
        pronunciations, to_index, from_grams, kind, n
    ):
    bit_sum = sum_all_bit_sums([
        name.bit_sums for name in pronunciations
    ], kind, n)
    ngram_checker = to_ngram_checker(
        to_index, from_grams
    )
    def full_list_matcher(grams):
        return ngram_checker(bit_sum, grams)
    return full_list_matcher 


def to_result_finder(
        pronunciations, to_index, from_grams, kind, n
    ):
    ngram_checker = to_ngram_checker(
        to_index, from_grams
    )
    def result_finder(grams):
        return set( 
            name_to_result(name) for name in pronunciations if (
                ngram_checker(name.bit_sums[kind][n], grams)
            )
        )
    return result_finder 


def unpack_results(packed, mon_list):
    return [
        mon_list[bit] for bit in 
        from_one_hot_encoding_sum(packed)
    ]


def pack_results(results):
    return to_one_hot_encoding_sum(
        result[0] for result in results
    )


def to_ruled_out_sum_filter(
        to_index, ruled_out_sum, n_i
    ):
    def ruled_out_sum_filter(ngram):
        return any(
            check_if_sum_has_index(
                ruled_out_sum, to_index(part)
            )
            for part in to_ngram_set(ngram, n_i)
        )
    return ruled_out_sum_filter


def to_rule_out(mappers, all_ngram_results, kind, n):
    for n_i in range(n, 0, -1):
        if (kind, n_i) not in all_ngram_results:
            continue
        ngram_results = all_ngram_results[(kind, n_i)]
        to_index = mappers.ngram_indexer(kind, n_i)
        parts = mappers.ngram_lists[kind][n_i]
        ruled_out_sum = to_one_hot_encoding_sum([
            bit for bit, part in enumerate(parts)
            if len(ngram_results[part]) == 0
        ])
        return to_ruled_out_sum_filter(
            to_index, ruled_out_sum, n_i
        )
    def no_filter(_):
        return False 
    return no_filter


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
            kind, n, ngram, ruled_out, log
        ) = threadpool_args
        find_in_full_list = full_list_matchers[(kind, n)]
        found = not ruled_out and find_in_full_list(
            Grams(**{ kind: ngram })
        )
        if not found:
            return ngram, set()
        log(ngram, ngram[0], kind, n)
        find_result = result_finders[(kind, n)]
        return ngram, find_result(
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
        rule_out = to_rule_out(
            mappers, all_ngram_results, kind, n
        )
        with ThreadPoolExecutor(n_threads) as threadpool:
            all_ngram_results[(kind, n)] = dict(
                threadpool.map(results_finder, [
                    (kind, n, ngram, rule_out(ngram), log)
                    for ngram in mappers.ngram_lists[kind][n]
                ])
            )
        print()
    return all_ngram_results


def index_results(
        all_ngram_results, substitutes, kind, n, ngram
    ):
    subs =  substitutes.get(kind, {}).get(n, {})
    ngram_results = all_ngram_results[(kind, n)]
    return ngram_results[subs.get(ngram, ngram)]


def to_results_merger(
        mappers, pronunciations, substitutes, checklist
    ):
    all_ngram_results = to_all_ngram_results(
        mappers, pronunciations, checklist.keys()
    )
    def results_merger(threadpool_args):
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
        results = set().union(*[
            index_results(
                all_ngram_results, substitutes, kind, n, ngram
            )
            for (kind, n), from_grams in checklist.items()
            for ngram in from_grams(grams)
        ])
        n_log_minimum = 10
        n_found = len(results)
        if n_found >= n_log_minimum:
            log(f'{grams.alphabet}: {n_found}', bigrams[0])
        return bigrams, Search(results=results, tail={})
    return results_merger


def index_search_results(
        mappers, pronunciations, substitutes
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
        ('alphabet', 2): to_alphabet_bigram_start,
        ('alphabet', 3): to_alphabet_trigram_end,
        ('arpepet', 3): to_all_arpepet_ngram_start(3),
        ('arpepet', 4): to_all_arpepet_ngrams(4)
    }
    print(
        'Finding results for:', ', '.join([
            f'{kind} {n}-grams' for kind, n in checklist
        ])
    )
    merge_results = to_results_merger(
        mappers, pronunciations, substitutes, checklist
    )
    print('\nFound ngram results. Finding search results...')
    search_index = {
        bigram: Search(tail={}, results=set())
        for bigram in mappers.ngram_lists['alphabet'][2]
    }
    log = to_lock_log()
    n_threads = mappers.n_threads
    with ThreadPoolExecutor(n_threads) as threadpool:
        searches = threadpool.map(merge_results, [
            (alphabet_4gram, log) for alphabet_4gram 
            in mappers.ngram_lists['alphabet'][4]
        ])
        for bigrams, search in searches:
            search_index[bigrams[0]].tail[bigrams[1]] = search
    print('\nFound search results.')
    return {
        k0: {
            k1: pack_results(v1.results)
            for k1,v1 in v0.tail.items()
        } 
        for k0,v0 in search_index.items()
    }

