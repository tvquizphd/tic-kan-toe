from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from search.service import to_service
from util import to_search_index
from util import to_fast_api

@asynccontextmanager
async def lifespan(
    _app: FastAPI
):
    # On start
    yield
    # On stop 

# Construct API
tvquiz_search = to_fast_api(lifespan=lifespan)

@tvquiz_search.get("/search/matches")
def get_matches(
        index=Depends(to_search_index), guess: str = '',
        max_gen: int | None = None
    ):
    gens = [1,2,3,4,5,6,7,8,9]
    if max_gen not in gens:
        max_gen = max(gens)
    return to_service(index).get_matches(guess, max_gen)
