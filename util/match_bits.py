# Return one-hot encodings of all possible ngrams
def to_match_bits(
        n: int, q: str,
        ngram_list: list[str],
        substitute_dict: dict[str, str]
    ):
    ngrams = set(
        ''.join(zipped) for zipped in zip(*[
            q[slice(n_i, None)] for n_i in range(n)
        ])
    )
    return sum(
        2**i for i,ngram in enumerate(ngram_list)
        if substitute_dict.get(ngram, ngram) in ngrams 
    )


