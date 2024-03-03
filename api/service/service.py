from urllib.parse import urlparse
from util import to_form_generations
from util import to_form_region_no_gimicks
from util import id_from_url
import requests
import logging
import json
import time

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

def format_mon(mon, forms):
    pokemon = {
        'forms': forms,
        'name': mon.name,
        'dex': mon.id 
    }
    return { 'pokemon': pokemon }

def clamp(v, low, high):
    return min(high, max(low, v))

class Service():
    def __init__(self, config):
        by_game_group = config.dex_map.by_game_group
        self.form_mon_dict = config.form_mon_dict
        self.gen_form_dict = config.gen_form_dict
        self.gen_mon_dict = config.gen_mon_dict
        self.by_game_group = by_game_group
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
                ver_id,
                id_from_url(ver["generation"]["url"]), [
                    id_from_url(dex["url"]) 
                    for dex in ver["pokedexes"]
                ], [
                    region["name"] for region in ver["regions"]
                ]
            ]))
            print('Adding', ver['name'])
        return version_list

    def run_test(self, form_id, fns):
        if form_id is None:
            return { 'ok': False }
        # Maximum maximum generation
        max_gen = max(self.generations)
        form = self.get_form(form_id, max_gen)
        # Form type conditions
        types = self.type_combos[form.type_combo]
        mon = self.form_mon_dict[form.form_id]
        ok_criteria = [
            t for t in types
        ] + [
            self.MONO for _ in [ types ]
            if len(types) == 1
        ]
        # First region condition
        ok_criteria += [
            to_form_region_no_gimicks(
                mon, self.by_game_group, form, 'SOME'
            )
        ]
        # Evaluate against valid conditions
        ok = all([
            fn(s, ok_criteria) for (s, fn) in fns
        ])
        if ok:
            ok_str = ','.join(ok_criteria)
            print(f'{form.name}: {ok_str}')
        return { 'ok': ok }

    def get_mon(self, dexn, gen=None):
        max_gen = gen if gen else max(self.generations)
        try:
            return self.gen_mon_dict[max_gen][dexn]
        except KeyError as e:
            print(e)
            return None

    def get_full_forms(self, dexn, gen=None):
        mon = self.get_mon(dexn, gen)
        if not mon: return None, []
        full_forms = [
            {
                'name': form.name,
                'id': form.form_id,
                'mon_id': form.mon_id,
                'generation': min(to_form_generations(
                    self.by_game_group, form, 'SOME'
                )),
            }
            for form in mon.forms
        ]
        return mon, full_forms

    def get_form(self, form_id, max_gen):
        return self.gen_form_dict[max_gen][form_id]

    def get_matches(self, raw_guess, max_gen):

        # No matches for 1 or 2 chars
        guess = raw_guess.lower()
        n_chars = len(guess)
        if n_chars <= 2:
            return []

        # Pokemon with same first 3 letters
        three = self.three_grams[max_gen].get(guess[:3], [])
        # Pokemon with same first 2 letters
        two = self.two_grams[max_gen].get(guess[:2], [])

        # Sort two-gram pokemon by match quality
        favored = sorted(
            two, reverse=True,
            key=lambda k: quality(*str_dist(guess, self.mon_name_dict[k]))
        )
        # List of all other pokemon
        full_dex = set(self.gen_mon_dict[max_gen].keys())
        etc = list(full_dex - set(two))
        # Sort other pokemon less exactly
        other = sorted(
            etc, reverse=True,
            key=lambda k: quality(*fast_dist(guess, self.mon_name_dict[k]))
        )

        out = []
        # Examples of trigrams:
        # common: cha, mag, dra, iro

        # Expansion TODO:
        # Possible to use n_partial in the future,
        # if more specific client-side requests are
        # needed per each form than stored in database
        # 
        # Few matches for short strings
        n_fetches, n_partial = (3, 0)
        # More matches for long strings 
        if n_chars > 3:
            n_fetches = clamp(len(three), 5, 10)
            #n_partial = clamp(len(two), 2, 10)
        
        root = self.api_url
        # Fetch some favored pokemon
        for _ in range(n_fetches):
            if not len(favored): break
            dexn = favored[0]
            favored.pop(0)
            mon, formated_forms = (
                self.get_full_forms(dexn, max_gen)
            )
            if mon: out.append((mon, formated_forms))

        # Pad out results with other partial matches
        for dexn in (favored + other)[:n_partial]:
            mon = self.get_mon(dexn, max_gen)
            if mon: out.append((mon, []))
        
        return [
            format_mon(mon, forms) for mon, forms in out
        ]


def to_service(config):
    return Service(config)
