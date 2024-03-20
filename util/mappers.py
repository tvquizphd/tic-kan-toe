from itertools import product
from multiprocessing import cpu_count
from typing import (
    Dict, List, Set, Callable
)
from g2p_en import G2p
from ipapy.arpabetmapper import ARPABETMapper
from pydantic import BaseModel
from .bit_sums import (
    sum_ngram_list_bits 
)

class Mappers(BaseModel):
    alphabet_n_sum_set: Set[int]
    arpepet_n_sum_set: Set[int]
    alphabet_list: List[str]
    arpepet_list: List[str]
    arpepet_table: Dict[str, str]
    arpepet_vowels: List[List[str]]
    arpepet_consonants: List[List[str]]
    ngram_lists: Dict[str, Dict[int, List[str]]]
    ipa_to_arpabet: Callable[[str], List[str]]
    alphabet_to_arpabet: Callable[[str], List[str]]
    n_threads: int
    
    def to_ngram_bits(self, kind, n, vals):
        return sum_ngram_list_bits(
            n, vals, self.ngram_lists[kind][n], {}
        )

    def sum_bits(self, alphabet_words, arpepet_words):
        return {
            'alphabet': {
                n: self.to_ngram_bits(
                    'alphabet', n, alphabet_words
                )
                for n in self.alphabet_n_sum_set
            },
            'arpepet': {
                n: self.to_ngram_bits(
                    'arpepet', n, arpepet_words
                )
                for n in self.arpepet_n_sum_set
            }
        }

    def ngram_indexer(self, kind, n):
        def to_index(ngram):
            return self.ngram_lists[kind][n].index(ngram)
        return to_index 

def to_mappers():
    all_letters = {
        'alphabet': list(
            'abcdefghijklmnopqrstuvwxyz'
        ),
        'arpepet': (
            'A E I O U Y T S R F H N P C'
        ).split(' ')
    }
    n_full_set = { 2, 3, 4 }
    return Mappers(
        alphabet_to_arpabet = G2p(),
        ipa_to_arpabet = (
            ARPABETMapper().map_unicode_string
        ),
        alphabet_n_sum_set = n_full_set,
        arpepet_n_sum_set = n_full_set,
        alphabet_list =  all_letters['alphabet'],
        arpepet_list =  all_letters['arpepet'],
        ngram_lists = {
            kind: {
                n: [
                    ''.join(ngram) for ngram in
                    product(letters, repeat=n)
                ]
                for n in n_full_set 
            }
            for kind, letters in all_letters.items()
        },
        arpepet_table = {
            'A': 'AA AO AH',
            'E': 'AE AX EH ER',
            'I': 'IH IY IX',
            'O': 'AW OW',
            'U': 'UH UW UX W WH',
            'Y': 'AY EY OY Y',
            'T': 'T D',
            'S': 'S SH Z ZH',
            'R': 'L R EL DX AXR',
            'F': 'DH TH F V',
            'H': 'G K HH Q',
            'N': 'M N NG NX EM EN',
            'P': 'B P',
            'C': 'CH JH'
        },
        arpepet_vowels = [
            ['Y','U'],
            ['I','O'],
            ['E','A'],
        ],
        arpepet_consonants = [
            ['P', 'T', 'H', 'N'],
            ['F', 'S', 'C', 'R']
        ],
        n_threads = max(1, min(8, cpu_count() // 2))
    )
