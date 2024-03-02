from pydantic import BaseSettings
from pydantic import BaseModel
from functools import lru_cache
from typing import Dict, List
from typing import Optional, Union
from models import unpackage_mon
from models import package_mon
from models import to_dex_map
from models import to_form
from models import to_mon
from models import Mon, Form
from models import DexMap 

from urllib.parse import urlparse
import requests
import logging
import json
import csv

CONFIG = {
    'MAIN_ENV': 'main.env.json',
    'GAMES': 'game-list.config.json',
    'TYPES': 'type-combos.config.json',
    'FORM_NAMES': 'extra-form-names.env.csv'
}
MONO = 'monotype'

def to_form_data(by_game_group, form, quantifier, key):
    found_game = False
    for group, data in by_game_group.items():
        if form.game_group == group:
            found_game = True
        if not found_game:
            continue
        for val in getattr(data, key):
            yield val
        # Strict only allows first game
        if quantifier != 'ALL': break
        # Subsequent games

def to_form_generations(*args):
    return to_form_data(*(args+('generations',)))

def to_form_regions(*args):
    return to_form_data(*(args+('regions',)))

def to_generations(by_game_group, mon, quantifier):
    for form in mon.forms:
        yield from to_form_generations(
            by_game_group, form, quantifier
        )

# TODO redundant in service.py
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

def to_valid_combos(mons, dex_map, type_combos):
    first_gens = dict()
    by_generation = dex_map.by_generation
    by_game_group = dex_map.by_game_group

    for mon in mons:
        for form in mon.forms:
            # Treat gimics as from their original games 
            gimics = ['mega', 'primal', 'origin', 'gmax']
            og_form = mon.forms[0] if (
                len([
                    None for part in form.name.split('-')
                    if part in gimics
                ])
            ) else form
            gens = list(to_form_generations(by_game_group, og_form, 'SOME'))
            regions = list(to_form_regions(by_game_group, og_form, 'SOME'))
            if not len(gens) or not len(regions):
                continue
            combo =(type_combos[form.type_combo])
            types = list(set(combo))
            # Pair any type with first region
            first_region = regions[0]
            grid_pairs = [
              tuple(sorted([first_region,t]))
              for t in types
            ] + [
                tuple(sorted(c)) for c in [combo]
                if len(c) == 2
            ] + [
                tuple(sorted(
                    [v, MONO]
                )) for c in [combo]
                for v in [*regions, c[0]]
                if len(c) == 1
            ]
            # Find first generation of pair
            all_gens = list(by_generation.keys())
            gen_limit = max(all_gens) + 1
            first_gen = min(gens)
            for c in grid_pairs:
                c_min_gen = first_gens.get(c, gen_limit)
                first_gens[c] = min(first_gen, c_min_gen)
    return {
        gen: sorted([
            c for c,v in first_gens.items() if v <= gen
        ])
        for gen in by_generation.keys()
    } 

def describe_type_combos(api_url):
    type_results = get_api(api_url, 'type/')['results']
    all_types = [ t['name'] for t in type_results ]
    def generate_types(all_types):
        for i,t1 in enumerate(all_types):
            for t2 in all_types[i:]:
                yield tuple(sorted(set([t1,t2])))

    # Ensure no duplicate types
    return sorted(set(generate_types(all_types)))

def get_form(form_id, type_combos, mon_id, api_url):
    f = get_api(api_url, f'pokemon-form/{form_id}/')
    type_names = tuple(sorted(set(
        t['type']['name'] for t in f.get('types', [])
    )))
    type_combo = type_combos.index(type_names)
    game_group = id_from_url(f['version_group']['url'])
    name = f['name']
    return to_form(
        name, form_id, type_combo, game_group, mon_id
    )

def get_forms(mon_id, type_combos, api_url):
    return [
        get_form(
            id_from_url(p['url']), type_combos, mon_id, api_url
        )
        for p in get_api(
            api_url, f'pokemon/{mon_id}/'
        )['forms']
    ]

def get_mon(dexn, dex_map, type_combos, api_url):
    pkmn = get_api(api_url, f'pokemon-species/{dexn}/')
    forms = [
        form 
        for v in pkmn.get('varieties', [])
        for form in get_forms(
            id_from_url(v['pokemon']['url']),
            type_combos, api_url
        )
    ]
    name = pkmn['name']
    return to_mon(dexn, forms, name)


def yield_alt_forms(mon):
    # Names of all forms but default
    for form in mon.forms[1:]:
        yield form.form_id, form.name


def describe_mon(dexn, dex_map, type_combos, api_url, todo=False):
    mon = get_mon(dexn, dex_map, type_combos, api_url)
    return package_mon(mon), list(yield_alt_forms(mon))


def to_ngrams(dex_map, mons):
    by_generation = dex_map.by_generation
    by_game_group = dex_map.by_game_group
    three_grams = dict()
    for mon in mons:
        for max_gen in by_generation.keys():
            gens = list(to_generations(by_game_group, mon, 'ALL'))
            name = mon.name
            mon_gen = min(gens) 
            if not mon_gen or mon_gen > max_gen: continue
            three = three_grams.get(max_gen, {})
            dex_list = three.get(name[:3], [])
            three[name[:3]] = dex_list + [
                mon.id
            ]
            three_grams[max_gen] = three

    two_grams = dict()
    for max_gen, three in three_grams.items():
        for k, v in three.items():
            two = two_grams.get(max_gen, {})
            two_list = two.get(k[:2], [])
            two[k[:2]] = two_list + v
            two_grams[max_gen] = two

    return (three_grams, two_grams)


def fill_gen_dicts(**kwargs):
    mons = kwargs['mons']
    by_generation = kwargs['dex_map'].by_generation
    by_game_group = kwargs['dex_map'].by_game_group
    gen_limit = 1 + max(by_generation.keys())
    gen_range = lambda min_gen: range(min_gen, gen_limit)
    for mon in mons:
        mon_origin_gen = min(
            to_generations(by_game_group, mon, 'SOME')
        )
        for gen in gen_range(mon_origin_gen):
            gen_dict = kwargs["gen_mon_dict"][gen]
            gen_dict[mon.id] = mon
        for form in mon.forms:
            form_origin_gen = min(
                to_form_generations(by_game_group, form, 'SOME')
            )
            for gen in gen_range(form_origin_gen):
                gen_dict = kwargs["gen_form_dict"][gen]
                gen_dict[form.form_id] = form
    return kwargs

def read_type_combos():
    try:
        with open(CONFIG['TYPES'], 'r') as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return []

def read_game_list():
    try:
        with open(CONFIG['GAMES'], 'r') as f:
            return json.loads(f.read())
    except FileNotFoundError:
        return []

def read_mon_list():
    try:
        with open(CONFIG['MAIN_ENV'], 'r') as f:
            kwargs = json.loads(f.read())
            return kwargs['mon_list']
    except FileNotFoundError:
        return []

def read_extra_form_names():
    try:
        with open(CONFIG['FORM_NAMES'], 'r') as f:
            form_reader = csv.reader(f, delimiter=',')
            for index,name in form_reader:
                yield int(index), name
    except FileNotFoundError:
        pass


@lru_cache()
def to_config():
    type_combos = list(read_type_combos())
    game_list = list(read_game_list())
    extra_form_name_dict = dict()
    for form_id, name in read_extra_form_names():
        extra_form_name_dict[form_id] = name

    with open(CONFIG['MAIN_ENV'], 'r') as f:
        kwargs = json.loads(f.read())
        kwargs['game_list'] = game_list
        kwargs['type_combos'] = type_combos
        kwargs['extra_form_name_dict'] = extra_form_name_dict
        dex_map = to_dex_map(kwargs['game_list'])
        generations = sorted(list(
            dex_map.by_generation.keys()
        ))
        mons = [
            unpackage_mon(packaged, extra_form_name_dict)
            for packaged in kwargs['mon_list']
        ]
        # All forms and mons per all max generations
        kwargs["gen_form_dict"] = {
            gen: dict() for gen in generations
        }
        kwargs["gen_mon_dict"] = {
            gen: dict() for gen in generations
        }
        kwargs["form_mon_dict"] = {
            form.form_id: mon
            for mon in mons for form in mon.forms
        }
        kwargs["mons"] = mons
        kwargs["dex_map"] = dex_map
        filled = fill_gen_dicts(**kwargs)
        kwargs["gen_mon_dict"] = filled['gen_mon_dict']
        kwargs["gen_form_dict"] = filled['gen_form_dict']
        # All ids per all 2 or 3 letter name prefixes
        (three_grams, two_grams) = to_ngrams(
            dex_map, mons 
        )
        kwargs["two_grams"] = two_grams
        kwargs["three_grams"] = three_grams
        kwargs["generations"] = generations 
        kwargs["valid_combos"] = to_valid_combos(
            mons, dex_map, kwargs['type_combos']
        )
        kwargs["mon_name_dict"] = {
            mon.id: mon.name for mon in mons
        }
        # Complete config derived from JSON
        return Config(
            MONO=MONO, **kwargs
        )

def set_config(**kwargs):
    extra_form_names = [*kwargs['extra_form_names']]
    type_combos = [*kwargs['type_combos']]
    game_list = [*kwargs['game_list']]
    del kwargs['extra_form_names']
    del kwargs['type_combos']
    del kwargs['game_list']
    with open(CONFIG['TYPES'], 'w') as f:
        f.write(json.dumps(type_combos)) 
    with open(CONFIG['GAMES'], 'w') as f:
        f.write(json.dumps(game_list)) 
    with open(CONFIG['FORM_NAMES'], 'w') as f:
        form_writer = csv.writer(f, delimiter=',')
        for form_id, name in extra_form_names:
            form_writer.writerow([form_id, name])
    with open(CONFIG['MAIN_ENV'], 'w') as f:
        f.write(json.dumps(kwargs)) 

class Ports(BaseModel):
    client: int
    api: int

Types = List[Union[
    tuple[str], tuple[str,str]
]]
PackagedGames = List[tuple[
    int, int, List[int], List[str]
]]
PackagedMons = List[List[Union[str, int]]]

class Config(BaseSettings):

    three_grams: Dict[int,Dict[str, List[int]]]
    two_grams: Dict[int,Dict[str, List[int]]]
    mon_name_dict: Dict[int, str]

    default_max_gen: int
    valid_combos: Dict[int, Types]
    generations: List[int]
    type_combos: Types 
    extra_form_name_dict: Dict[int, str]
    gen_form_dict: Dict[int, Dict[int, Form]]
    gen_mon_dict: Dict[int, Dict[int, Mon]]
    form_mon_dict: Dict[int, Mon]
    game_list: PackagedGames
    mon_list: PackagedMons 
    mons: List[Mon]
    dex_map: DexMap
    ports: Ports
    api_url: str
    MONO: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
