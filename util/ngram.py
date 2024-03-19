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


def to_alphabet_bigram_start(grams: Grams):
    if len(grams.alphabet) < 2:
        return set()
    return set([grams.alphabet[:2]])


def to_alphabet_trigram_end(grams: Grams):
    if len(grams.alphabet) < 3:
        return set()
    return set([grams.alphabet[-3:]])


def to_all_arpepet_ngram_start(subs, n):
    def to_ngram_start(grams: Grams):
        arpepet = subs.get(
            grams.arpepet, grams.arpepet
        )
        if len(arpepet) < n:
            return set()
        return set([ arpepet[:n] ])
    return to_ngram_start


def to_all_arpepet_ngrams(subs, n):
    def to_ngrams(grams: Grams):
        arpepet = subs.get(
            grams.arpepet, grams.arpepet
        )
        if len(arpepet) < n:
            return set()
        return to_ngram_set(arpepet, n)
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
