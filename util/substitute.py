from itertools import product 

def to_arpepet_variant(mappers, phone):
    phone_matrix, idx1, idx2 = (None, None, None)
    matrices = (
        mappers.arpepet_vowels, mappers.arpepet_consonants
    )
    for matrix in matrices:
        vector = [value for row in matrix for value in row]
        width = len(matrix[0])
        try:
            flat_idx = vector.index(phone)
            idx1, idx2 = divmod(flat_idx, width)
            phone_matrix = matrix
            break
        except ValueError:
            pass
    if phone_matrix is None:
        return []
    # Options
    return set(
        value
        for i1,row in enumerate(phone_matrix)
        for i2,value in enumerate(row)
        if (idx2 == i2 or idx1 == i1)
        and value != phone
    )


def to_arpepet_variants(mappers, reviewers, phone):
    vowels = [
        v for row in mappers.arpepet_vowels for v in row
    ]
    variants = []
    for index, char in enumerate(list(phone)):
        for char_out in to_arpepet_variant(mappers, char):
            phone_out = ''.join([
                char_out if i == index else x
                for i,x in enumerate(list(phone))
            ])
            variants.append((
                int(phone_out[index] in vowels),
                reviewers.rate_phonotactics(phone_out),
                phone_out
            ))
    return [v[-1] for v in sorted(variants, reverse=True)]


def resize_phone(mappers, reviewers, bad_phone, n):
    diff = max(0, n - len(bad_phone))
    if diff == 0:
        return [(bad_phone, bad_phone[:n])]
    good_phones = [
        bad_phone + ''.join(args)
        for args in product(
            mappers.arpepet_table.keys(), repeat=diff
        )
    ]
    return [(bad_phone, v[-1]) for v in sorted([
        (reviewers.rate_phonotactics(phone), phone)
        for phone in good_phones
    ], reverse=True)]


def iterate_ngram_substitutes(
        mappers, reviewers, valid_phones, n
    ):
    phone_pairs = (
        pair for n_i in range(1, n+1) for args in product(
            mappers.arpepet_table.keys(), repeat=n_i
        )
        for pair in resize_phone(
            mappers, reviewers, ''.join(args), n
        )
    )
    for bad_phone, phone in phone_pairs:
        if phone in valid_phones:
            yield bad_phone, phone
        variants = to_arpepet_variants(
            mappers, reviewers, phone
        )
        for variant in variants:
            if variant in valid_phones:
                yield bad_phone, variant

def to_ngram_substitutes(*args):
    return dict(iterate_ngram_substitutes(*args))
