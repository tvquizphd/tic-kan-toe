import math
from statistics import mean
from itertools import accumulate

def evaluate_break(phone_list, word_breaks, index, pre, post):
    post_zip = list(zip(phone_list[index:], post))
    pre_zip = list(
        zip(phone_list[:index][::-1], pre[::-1])
    )[::-1]
    same_first_post = len(post_zip) > 0 and (
        1 == len(set(post_zip[0]))
    )
    # Prioritize word-break, then post, then pre
    at_word_break = len(word_breaks) >= 1 and 0 == min(
        abs(index - space) for space in word_breaks
    )
    return (
        int(at_word_break),
        int(same_first_post),
        sum(word_c == c for word_c, c in post_zip),
        sum(word_c == c for word_c, c in pre_zip)
    )


def find_syllable_breaks(word_breaks, syllables, phone_list):
    min_syllable_phones = 2
    break_start = 0
    break_index = 0
    index_sum = sum(
        len(syllable) for syllable in syllables
    )
    for pre, post in zip(
        syllables[:-1], syllables[1:]
    ):
        # Convert input to output index
        break_index += len(pre)
        break_choices = []
        starts = set(word_breaks + [
            nearest(len(phone_list) * (
                break_index / index_sum
            ))
            for nearest in [math.floor, math.ceil]
        ])
        for start in starts:
            smallest_margin = min(
                start, len(phone_list) - start,
                start - break_start
            )
            if smallest_margin < min_syllable_phones:
                continue
            break_choices.append(evaluate_break(
                phone_list, word_breaks, start, pre, post
            ) + (start,))
        if len(break_choices) < 1:
            break_start = round(len(phone_list) * (
                break_index / index_sum
            ))
            continue
        choice = sorted(
            break_choices, reverse=True
        )[0]
        break_start = choice[-1]
        yield choice


def match_syllables(syllables, words):
    phone_list = [
        phone for word in words
        for phone in word
    ]
    word_breaks = list(accumulate([
        len(word) for word in words
    ]))[:-1]
    # 1 to 7: 1 break, 8 to 11: 2 breaks
    n_breaks_out = max(1,len(phone_list) // 4)
    best_breaks = sorted(
        find_syllable_breaks(
            word_breaks, syllables, phone_list
        ),
        reverse=True
    )
    if len(best_breaks) == 0:
        return [ ''.join(phone_list) ]
    starts = sorted([
        x[-1] for x in best_breaks
    ][:n_breaks_out])
    return [
        ''.join(phone_list[slice(*pair)]) for pair in zip(
            [0] + starts, starts + [None]
        )
    ]


def partitions(s, min_chars=2):
    if len(s) > 0:
        for i in range(min_chars, len(s)+1):
            first, rest = s[:i], s[i:]
            for p in partitions(rest, min_chars):
                yield [first] + p
    else:
        yield []


def invent_syllables(
    reviewers, arpepet_word, max_syllables
    ):
    options = sorted([
        (
            mean(
                reviewers.rate_phonotactics(syllable)
                for syllable in partition
            ),
            *partition
        )
        for partition in partitions(arpepet_word)
        if len(partition) <= max_syllables
    ], reverse=True)
    return options[0][1:]
