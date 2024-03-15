from itertools import (
    product, chain
)

def to_arpepet_variant(
    arpepet_vowels, arpepet_consonants, phone
    ):
    phone_matrix, idx1, idx2 = (None, None, None)
    for matrix in (arpepet_vowels, arpepet_consonants):
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


def to_arpepet_variants(
    arpepet_vowels, arpepet_consonants,
    rate_phonotactics, phones
    ):
    vowels = [
        v for row in arpepet_vowels for v in row
    ]
    variants = []
    for index, phone_in in enumerate(list(phones)):
        for phone_out in to_arpepet_variant(
            arpepet_vowels, arpepet_consonants, phone_in
        ):
            phones_out = ''.join([
                phone_out if i == index else x
                for i,x in enumerate(list(phones))
            ])
            variants.append((
                int(phone_in not in vowels),
                rate_phonotactics(phones_out),
                phones_out
            ))
    return [v[-1] for v in sorted(variants, reverse=False)]



def handle_missing_phones(
        mappers, reviewers, valid_phones,
        substitute_dict, n
    ):
    missing_phones = [
        ''.join(chain(args)) for args in product(
            mappers.arpepet_table.keys(), repeat=n
        )
        if ''.join(chain(args)) not in valid_phones
    ]
    for missing_phone in missing_phones:
        for args in substitute_dict.items():
            replaced = missing_phone.replace(*args)
            if replaced in valid_phones:
                yield missing_phone, replaced
                continue

        variants = to_arpepet_variants(
            mappers.arpepet_vowels,
            mappers.arpepet_consonants,
            reviewers.rate_phonotactics,
            missing_phone
        )
        for variant in variants:
            if variant in valid_phones:
                yield missing_phone, variant
                break


def to_ngram_substitutes(
        n, mappers, reviewers, valid_phones
    ):
    n_phones = [
        phones for phones in valid_phones if len(phones) == n
    ]
    two_phones = [
        phones for phones in valid_phones if len(phones) == 2
    ]
    substitute_dict_2grams = dict(handle_missing_phones(
        mappers, reviewers, two_phones, {}, n=2
    ))
    if n == 2:
        return substitute_dict_2grams
    return dict(handle_missing_phones(
        mappers, reviewers, n_phones,
        substitute_dict_2grams, n=n
    ))
