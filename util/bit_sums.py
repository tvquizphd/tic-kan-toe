from functools import reduce
from .ngram import to_ngram_set

BitSums = dict[str, dict[int, int]]


def bitwise_and(bit_list):
    return reduce(lambda x, y: x & y, bit_list, 0)


def bitwise_or(bit_list):
    return reduce(lambda x, y: x | y, bit_list, 0)


def to_one_hot_encoding_sum(integers: list[int]):
    return bitwise_or( 1 << i for i in integers )


def from_one_hot_encoding(packed: int):
    return [
        bit for bit in range(packed.bit_length())
        if check_if_sum_has_index(packed, bit)
    ]


def check_if_sum_has_index(packed: int, bit: int):
    return ((1 << bit) & packed) > 0

def sum_ngram_bits(
        n: int, q: str, all_ngrams: list[str],
        substitutes: dict[str, str]
    ):
    ngrams = to_ngram_set(q, n)
    return to_one_hot_encoding_sum(
        i for i,ngram in enumerate(all_ngrams)
        if substitutes.get(ngram, ngram) in ngrams 
    )

def sum_ngram_list_bits(
        n: int, qs: list[str], all_ngrams: list[str],
        substitutes: dict[str, str]
    ):
    return bitwise_or(
        sum_ngram_bits(n, q, all_ngrams, substitutes)
        for q in qs
    )

def sum_all_bit_sums(
    all_bit_sums: list[BitSums], kind: str, n: int
):
    return bitwise_or(
        bit_sums[kind][n] for bit_sums in all_bit_sums
    )
