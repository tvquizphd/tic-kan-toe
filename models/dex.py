import functools
from collections import defaultdict
from typing import Dict, List
from pydantic import BaseModel

class Dex(BaseModel):
    regions: List[str]
    game_group: int
    generation: int
    id: int

class GenerationData(BaseModel):
    game_groups: List[int]
    regions: List[str]
    dexes: List[Dex]

class GameGroupData(BaseModel):
    generations: List[int]
    regions: List[str]
    dexes: List[Dex]

class RegionData(BaseModel):
    generations: List[int]
    game_groups: List[int]
    dexes: List[Dex]

class DexMap(BaseModel):
    by_region: Dict[str, RegionData]
    by_game_group: Dict[int, GameGroupData]
    by_generation: Dict[int, GenerationData] 

def to_dexes(game:list[int, int, list[int], list[str]]):
    game_group, generation, dex_ids, regions = game
    return [
        Dex(
            id=id, regions=regions,
            generation=generation,
            game_group=game_group
        )
        for id in dex_ids
    ]


def to_dex_map(
    games: list[list[int, int, list[int], list[str]]]
) -> DexMap:
    def from_games(
        dicts: dict[str, list[Dex]],
        game: list[int, int, list[int], list[str]]
    ):
        def update(k1,k2):
            ids = [ v.id for v in dicts[k1][k2] ]
            dicts[k1][k2] = (
                dicts[k1][k2] + [
                    dex for dex in to_dexes(game)
                    if dex.id not in ids 
                ]
            )
        game_group, generation, _, regions = game
        update('generations', generation)
        update('game_groups', game_group)
        for region in regions:
            update('regions', region)
        return dicts
    dicts = functools.reduce(from_games, games, {
        "regions": defaultdict(list),
        "game_groups": defaultdict(list),
        "generations": defaultdict(list)
    })
    by_game_group = {
        game_group: GameGroupData(
            dexes=dexes,
            regions=list(set(
                region for dex in dexes
                for region in dex.regions
            )),
            generations=list(set(
                dex.generation for dex in dexes
            ))
        ) for game_group, dexes
        in dicts['game_groups'].items()
    }
    by_generation = {
        generation: GenerationData(
            dexes=dexes,
            regions=list(set(
                region for dex in dexes
                for region in dex.regions
            )),
            game_groups=list(set(
                dex.game_group for dex in dexes
            ))
        ) for generation, dexes
        in dicts['generations'].items()
    }
    by_region = {
        region: RegionData(
            dexes=dexes,
            generations=list(set(
                dex.generation for dex in dexes
            )),
            game_groups=list(set(
                dex.game_group for dex in dexes
            ))
        ) for region, dexes
        in dicts['regions'].items()
    }
    return DexMap(
        by_region=by_region,
        by_generation=by_generation,
        by_game_group=by_game_group
    )
