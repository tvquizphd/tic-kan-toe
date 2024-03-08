#from util import (
#    get_api
#)

class Service():
    def __init__(self, index):
        pass

    def get_matches(self, raw_guess, max_gen):

        # No matches for 1 or 2 chars
        print(max_gen)
        guess = raw_guess.lower()
        n_chars = len(guess)
        if n_chars <= 2:
            return []
        return []


def to_service(config):
    return Service(config)
