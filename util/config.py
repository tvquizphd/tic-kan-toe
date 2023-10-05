from pydantic import BaseSettings
from pydantic import BaseModel
from functools import lru_cache
from typing import Dict, List
from typing import Optional, Union

from urllib.parse import urlparse
import requests
import logging
import json

CONFIG = 'env.json'
MONO = 'monotype'

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

def to_valid_combos(gens, mon_list, game_list, type_combos):
    first_gens = dict()
    for mon in mon_list:
        if not mon[2]: continue
        gen = min(mon[2].values())
        regions = list(mon[2].keys())
        typing = type_combos[mon[1][0]]
        grid_pairs = [
          tuple(sorted([r,t]))
          for t in typing for r in regions
        ]
        if len(typing) == 2:
            grid_pairs.append(tuple(typing))
        else:
            grid_pairs += [
                tuple(sorted([v, MONO]))
                for v in [*regions, typing[0]]
            ]
        for c in grid_pairs:
            c_min_gen = first_gens.get(c,max(gens)+1)
            first_gens[c] = min(gen, c_min_gen)
    return {
        gen: sorted([
            c for c,v in first_gens.items() if v <= gen
        ])
        for gen in gens 
    } 

def to_all_regions(game_list):
    game_regions = [
        (game[0], region)
        for game in game_list
        for region in game[2]
    ]
    all_regions = []

    for region in game_regions:
        region_names = [r[1] for r in all_regions]
        if region[1] not in region_names:
            all_regions.append(region)

    return all_regions

def describe_type_combos(api_url):
    type_results = get_api(api_url, 'type/')['results']
    all_types = [ t['name'] for t in type_results ]
    def generate_types(all_types):
        for i,t1 in enumerate(all_types):
            for t2 in all_types[i:]:
                yield tuple(sorted(set([t1,t2])))

    # Ensure no duplicate types
    return sorted(set(generate_types(all_types)))

def describe_mon(dexn, game_list, type_combos, api_url):

    gen_dict = parse_generations(game_list)
    all_regions = to_all_regions(game_list)
    pre_config = PreConfig(
        gen_dict=gen_dict, all_regions=all_regions
    )

    def form_to_species(pkmn):
        species_id = id_from_url(pkmn["species"]["url"])
        return get_api(api_url, f'pokemon-species/{species_id}/')

    def to_regional_dex_list(pkmn):
        species = form_to_species(pkmn)
        gen_id = id_from_url(species["generation"]["url"])
        gen_list = pre_config.gen_dict[gen_id]
        dex_list = [
            did for game in gen_list
            for did in game[1]
        ]
        # Return all sorted dex IDs
        return list(sorted(set(dex_list)))

    def to_first_region(pkmn_id, pkmn):
        name = pkmn['name']
        print(pre_config.all_regions)
        region_dict = {
            r: g for g,r in set(pre_config.all_regions)
        }
        # Use any region found in name
        for region_name in name.split('-'):
            if region_name in region_dict:
                generation = region_dict[region_name]
                print(f'#{pkmn_id} {name} from {region_name}')
                return { region_name: generation }
        # Use first pokedex if no region in name
        for did in to_regional_dex_list(pkmn):
            dex = get_api(api_url, f'pokedex/{did}/')
            region_name = dex['region']['name']
            dex_species = [
                id_from_url(d['pokemon_species']['url'])
                for d in dex['pokemon_entries']
            ]
            # Pokemon not in this regional dex
            if pkmn_id not in dex_species:
                continue
            if region_name not in region_dict:
                continue
            generation = region_dict[region_name]
            print(f'#{pkmn_id} {name} from {region_name}')
            return { region_name: generation }
        return None

    pkmn = get_api(api_url, f'pokemon/{dexn}/')
    type_combo = tuple(sorted(set([
        t['type']['name'] for t in pkmn.get('types', [])
    ])))
    type_combo_index = type_combos.index(type_combo)
    # TODO: multiple types per pokemon (variants)?
    return (
        pkmn['name'], [type_combo_index],
        to_first_region(dexn, pkmn)
    )


def parse_generations(game_list):
    all_gen_ids = set([
       game[0] for game in game_list
    ])
    gen_dexes = {
        gen: [
            game for game in game_list
            if gen == game[0]
        ]
        for gen in list(all_gen_ids)
    }
    return gen_dexes

def to_ngrams(gens, mon_list):
    three_grams = dict()
    for dexn,mon in enumerate(mon_list, 1):
        for max_gen in gens:
            name = mon[0]
            mon_gen = min((mon[2] or {'': -1}).values())
            if mon_gen > max_gen: continue
            three = three_grams.get(max_gen, {})
            dex_list = three.get(name[:3], [])
            three[name[:3]] = dex_list + [dexn]
            three_grams[max_gen] = three

    two_grams = dict()
    for max_gen, three in three_grams.items():
        for k, v in three.items():
            two = two_grams.get(max_gen, {})
            two_list = two.get(k[:2], [])
            two[k[:2]] = two_list + v
            two_grams[max_gen] = two

    return (three_grams, two_grams)

@lru_cache()
def to_config():
    with open(CONFIG, 'r') as f:
        kwargs = json.loads(f.read())
        kwargs["mon_name_dict"] = {
            dexn: mon[0] for dexn,mon
            in enumerate(kwargs['mon_list'], 1)
        }
        (three_grams, two_grams) = to_ngrams(
            kwargs['generations'], kwargs['mon_list']
        )
        kwargs["two_grams"] = two_grams
        kwargs["three_grams"] = three_grams
        kwargs["all_regions"] = to_all_regions(
            kwargs['game_list']
        )
        kwargs["valid_combos"] = to_valid_combos(
            kwargs['generations'], kwargs['mon_list'],
            kwargs['game_list'], kwargs['type_combos']
        )
        # Complete config derived from JSON
        return Config(
            MONO=MONO, **kwargs
        )

def set_config(**kwargs):
    with open(CONFIG, 'w') as f:
        f.write(json.dumps(kwargs)) 

class Ports(BaseModel):
    client: int
    api: int

Types = List[Union[
    tuple[str], tuple[str,str]
]]
Games = List[tuple[
    int, List[int], List[str]
]]
Mons = List[tuple[
    str, List[int], Optional[Dict[str, int]]
]]

class PreConfig(BaseSettings):
    gen_dict: Dict[int, Games]
    all_regions: List[tuple[int, str]]

class Config(BaseSettings):

    three_grams: Dict[int,Dict[str, List[int]]]
    two_grams: Dict[int,Dict[str, List[int]]]
    mon_name_dict: Dict[int, str]

    default_max_gen: int
    all_regions: List[tuple[int, str]]
    valid_combos: Dict[int, Types]
    generations: List[int]
    type_combos: Types 
    game_list: Games
    mon_list: Mons 
    ports: Ports
    api_url: str
    MONO: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
