from urllib.parse import urlparse
import requests
import logging
import json
import time

# TODO redundant in config.py
def id_from_url(url):
    split_url = urlparse(url).path.split('/')
    return int([s for s in split_url if s][-1])

def get_api(root, endpoint, unsure=False):
    headers = {'content-type': 'application/json'}
    try:
        r = requests.get(root + endpoint, headers=headers)
        return r.json() 
    except Exception as e:
        if not unsure:
            logging.critical(e, exc_info=True)
        return None

def get_pages(root, endpoint, offset=None):
    off = f"&offset={offset}" if offset else ""
    page_list = get_api(root, f'/{endpoint}/?limit=1000{off}')
    while page_list["next"] is not None:
        next_list = get_api(
            root, f'/{endpoint}/?{urlparse(page_list["next"]).query}'
        )
        page_list["results"].append(next_list["results"])
        page_list["next"] = next_list["next"]

    return page_list

def quality(offset, n, count):
    is_first = offset == 0
    scales = [
        [0, 0], [10*2**n, n]
    ][+(n>0)]
    values = [is_first, count]
    ranking = zip(scales, values)
    return sum([p*v for p,v in ranking])

def to_ngrams(s,n):
    for start in range(0, len(s) - n + 1):
        yield s[start:start+n]

def to_ngram_union(guess, target, n):
    ngrams_guess = set(to_ngrams(guess, n))
    ngrams_target = set(to_ngrams(target, n))
    union = ngrams_guess & ngrams_target
    offset = 0 if not len(union) else min(
        target.index(un) for un in union
    )
    return (union, offset)

def fast_dist(guess, target):

    found = (0, 0, 0)

    for n in [1,2,3]:
        (union, offset) = to_ngram_union(guess, target, n)
        if len(union) == 0: continue
        found = (offset, n, len(union))

    return found 

def str_dist(guess, target):

    found = (0, 0, 0)

    for n in [1,2,3,4,5,6]:
        (union, offset) = to_ngram_union(guess, target, n)
        if len(union) == 0: continue
        found = (offset, n, len(union))

    return found 

def format_form(v, generation):
    pid = id_from_url(v['url'])
    form = {
        'name': v['name'], 'id': pid,
        'generation': generation,
    }
    return { 'form': form }

def format_pkmn(p):
    varieties = [v['pokemon'] for v in p.get('varieties', [])]
    gen = p['generation']
    forms = [
        format_form(v, gen)['form'] for v in varieties
    ]
    pokemon = {
        'forms': forms,
        'name': p['name'],
        'dex': p['id']
    }
    return { 'pokemon': pokemon }

def clamp(v, low, high):
    return min(high, max(low, v))

class Service():
    def __init__(self, config):
        self.mon_dict = {
            gen: {
                i:v for i,v in enumerate(config.mon_list,1)
                if min((v[2] or {'': -1}).values()) <= gen
            }
            for gen in config.generations
        }
        self.generations = config.generations
        self.mon_name_dict = config.mon_name_dict
        self.type_combos = config.type_combos
        self.three_grams = config.three_grams
        self.two_grams = config.two_grams
        self.api_url = config.api_url
        self.MONO = config.MONO

    async def delete_api(self, endpoint):
        #target = self.api_url + endpoint
        #session.delete(target)
        pass

    async def put_api(self, endpoint, data):
        #target = self.api_url + endpoint
        headers = {'content-type': 'application/json'}
        #session.put(target, json=data, headers=headers)
        pass

    async def post_api(self, endpoint, data):
        #target = self.api_url + endpoint
        headers = {'content-type': 'application/json'}
        #session.post(target, json=data, headers=headers)
        pass

    @staticmethod 
    def update_games(root, games):
        new_ver_list = get_pages(
            root, 'version-group', len(games)
        )
        version_list = [ *games ]
        for ver_info in new_ver_list["results"]:
            ver_id = id_from_url(ver_info['url'])
            ver = get_api(root, f'/version-group/{ver_id}')
            version_list.append(tuple([
                id_from_url(ver["generation"]["url"]), [
                    id_from_url(dex["url"]) 
                    for dex in ver["pokedexes"]
                ], [
                    region["name"] for region in ver["regions"]
                ]
            ]))
            print('Adding', ver['name'])
        return version_list

    def run_test(self, identifier, fns):
        root = self.api_url
        pkmn = get_api(root, f'pokemon/{identifier}/')
        dexn = id_from_url(pkmn["species"]["url"])
        max_max = max(self.generations)
        mon = self.mon_dict[max_max][dexn]
        types = list(
            self.type_combos[mon[1][0]]
        )
        # Find original region
        regions = list((mon[2] or { }).keys())
        
        # All conditions met within all types
        conditions = []
        if len(types) == 1:
            conditions.append(self.MONO)
        valid = (
            types + regions + conditions
        )
        ok = all([fn(s,valid) for (s,fn) in fns])
        if ok:
            print(f'{pkmn["name"]}:', ','.join(valid))
        return { 'ok': ok }

    def parse_forms(self, pkmn):
        varieties = [
            v['pokemon'] for v in pkmn.get('varieties', [])
        ]
        gens = self.generations
        # Find pokemon regions dict
        mon = self.mon_dict[max(gens)][
            int(pkmn['id'])
        ]
        region_dict = mon[2]
        gen = (
            min(region_dict.values())
            if len(region_dict) else -1
        )
        return [
            format_form(v, gen) for v in varieties
        ]

    def get_forms(self, dexn):
        root = self.api_url
        pkmn = get_api(root, f'pokemon-species/{dexn}/', True)
        return self.parse_forms(pkmn)

    def get_matches(self, raw_guess, max_gen):

        start_request = time.time()
        guess = raw_guess.lower()

        min_chars = 2
        n_chars = len(guess)
        bonus_chars = n_chars - min_chars
        if bonus_chars < 0:
            return []

        # Example trigrams: cha, mag, dra, iro
        two = self.two_grams[max_gen].get(guess[:2], [])
        three = self.three_grams[max_gen].get(guess[:3], [])

        # Sort two-gram pokemon by match quality
        favored = sorted(
            two, reverse=True,
            key=lambda k: quality(*str_dist(guess, self.mon_name_dict[k]))
        )
        # List of all other pokemon
        full_dex = set(self.mon_dict[max_gen].keys())
        etc = list(full_dex - set(two))
        # Sort other pokemon less exactly
        other = sorted(
            etc, reverse=True,
            key=lambda k: quality(*fast_dist(guess, self.mon_name_dict[k]))
        )

        out = []
        ntri = len(three)
        # Increase results by string length
        defaults = (2, clamp(ntri, 2, 12))
        (n_fetches, n_partial) = ({
            0: (1, 2),
            1: (1, 4),
            2: (2, clamp(ntri, 1, 8)),
        }).get(bonus_chars, defaults)

        root = self.api_url
        # Fetch some favored pokemon
        for _ in favored[:n_fetches]:
            dexn = favored[0]
            # Search for pokemon if not tried
            pkmn = get_api(root, f'pokemon-species/{dexn}/', True)
            if pkmn is None: continue
            gen = id_from_url(pkmn['generation']['url'])
            forms = self.parse_forms(pkmn)
            favored = favored[1:]
            out.append({
                'name': pkmn['name'],
                'id': pkmn['id'],
                'generation': gen,
                'forms': forms
            })

        main_out = len(out)

        # Pad out results with other matches
        for dexn in (favored + other)[:n_partial]:
            mon = self.mon_dict[max_gen][dexn]
            gen = min((mon[2] or {'': -1}).values())
            name = mon[0]
            pkmn = { 
                'name': name, 'id': dexn,
                'generation': gen
            }
            out.append(pkmn)
        
        end_request = time.time()
        return [format_pkmn(p) for p in out]


def to_service(config):
    return Service(config)
