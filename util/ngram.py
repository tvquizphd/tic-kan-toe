from typing import Union
from itertools import product
from pydantic import BaseModel

class Grams(BaseModel):
    alphabet: Union[str,None]
    arpepet: Union[str,None]


def to_alphabet_ngram(grams: Grams):
    return set([grams.alphabet])


def to_arpepet_ngram(grams: Grams):
    return set([grams.arpepet])


def to_alphabet_ngram_start(n):
    def to_ngram_start(grams: Grams):
        if len(grams.alphabet) < n:
            return set()
        return set([ grams.alphabet[:n] ])
    return to_ngram_start


def to_arpepet_ngram_start(subs, n):
    def to_ngram_start(grams: Grams):
        arpepet = subs.get(
            grams.arpepet, grams.arpepet
        )
        if len(arpepet) < n:
            return set()
        return set([ arpepet[:n] ])
    return to_ngram_start


def to_all_alphabet_ngrams(n):
    def to_ngrams(grams: Grams):
        return to_ngram_set(grams.alphabet, n)
    return to_ngrams


def to_all_ngrams(items, n):
    return [
        ''.join(i) for i in product(items, repeat=n)
    ]

def to_ngram_set(q, n):
    return set(
        ''.join(zipped) for zipped in zip(*[
            q[slice(n_i, None)] for n_i in range(n)
        ])
    )
