from .mappers import Mappers

def with_only_arpabet(word):
    # Two-character arpabet always upper case
    return "".join(
        x for x in word if
        x.isalpha() and x.isupper()
    )

def arpabet_to_arpepet(arpepet_table, arpa_list):
    converter = {
        arpa_key: arpe_key
        for arpe_key, arpa_str in (arpepet_table).items()
        for arpa_key in arpa_str.split(' ')
    }
    for arpa_phone in arpa_list:
        arpa = with_only_arpabet(arpa_phone)
        # Handle non-standard arpabet
        if arpa not in converter:
            yield from ({
                'EA': ['E', 'R'],
                'IA': ['I', 'R']
            }).get(arpa, list(arpa))
            continue
        yield converter[arpa]

def alphabet_to_arpepet(mappers: Mappers, word: str):
    return list(arpabet_to_arpepet(
        mappers.arpepet_table,
        mappers.alphabet_to_arpabet(word)
    ))

def ipa_to_arpepet(mappers: Mappers, ipa_word: str):
    return list(arpabet_to_arpepet(
        mappers.arpepet_table,
        mappers.ipa_to_arpabet(
            ipa_word, ignore=True,
            return_as_list=True
        )
    ))
