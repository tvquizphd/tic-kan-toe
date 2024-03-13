from typing import (
    Dict, Set, Tuple
)
from pydantic import BaseModel
from .match_bits import to_match_bits
from .mappers import Mappers
from .arpepet import (
    alphabet_to_arpepet 
)

Result = Tuple[int, int, int]

class Search(BaseModel):
    results: Set[Result]
    tail: Dict[str, 'Search']
Search.update_forward_refs()


def to_results(
        mappers: Mappers, kind: str, n: int, q: str,
        results: set[tuple[int, int, int]],
        substitute_dict: dict[str, str] = None
    ):
    index, ngrams = ({
        ('alphabet', 2): (1, mappers.alphabet_ngram_lists[2]),
        ('arpepet', 4): (2, mappers.arpepet_ngram_lists[4])
    }).get((kind, n))
    ngram_bits = to_match_bits(
        n, q, ngrams, substitute_dict or {}
    )
    return set(
        result for result in results if (
            ngram_bits & result[index] 
        ) > 0
    )


def unpack_results(packed, mon_list):
    return [
        mon for mon in mon_list
        if (2**mon.id & packed) != 0
    ]


def pack_results(results):
    return sum(
        2**result[0] for result in results
    )


def index_search_results(
        mappers, pronunciations,
        substitute_dict_4grams
    ):
    all_bigram_bits = sum(
        name.alphabet_match_bits[2]
        for name in pronunciations
    )
    possible_results = set(
        (
            name.id,
            name.alphabet_match_bits[2],
            name.arpepet_match_bits[4]
        )
        for name in pronunciations
    )
    search_index = {
        bigram: Search(tail={}, results=set())
        for bigram in mappers.alphabet_ngram_lists[2]
    }
    todo = set()
    for q in mappers.alphabet_ngram_lists[4]:
        bigrams = [
            a+b for a,b in zip(q, q[1:])
        ]
        if bigrams[0] not in todo:
            todo.add(bigrams[0])
            print(bigrams[0], flush=True)
        ok = (
            0 < (
                2**mappers.alphabet_ngram_lists[2].index(bigram)
                & all_bigram_bits
            )
            for bigram in bigrams
        )
        # Require 1st bigram, or either subsequent 
        if next(ok) or (next(ok) and next(ok)):
            q_phones = ''.join(
                alphabet_to_arpepet(mappers, q)
            )
            alphabet_results = to_results(
                mappers, 'alphabet', 2, q,
                possible_results, {}
            )
            arpepet_results = to_results(
                mappers, 'arpepet', 4, q_phones,
                possible_results, substitute_dict_4grams
            )
            results = arpepet_results.union(alphabet_results)
            search_index[bigrams[0]].tail[bigrams[2]] = (
                Search(results=results, tail={})
            )
    return {
        k0: {
            k1: pack_results(v1.results)
            for k1,v1 in v0.tail.items()
        } 
        for k0,v0 in search_index.items()
    }

