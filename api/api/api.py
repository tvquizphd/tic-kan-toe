import asyncio
from contextlib import asynccontextmanager
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from fastapi import Depends, FastAPI, WebSocket
from api.service import to_service
from util import to_multiplayer
from util import to_config
from util import to_fast_api

@asynccontextmanager
async def lifespan(
    _app: FastAPI
):
    # Initialize Multiplayer
    multiplayer = to_multiplayer()
    # Any startup costs before yield
    yield
    # Signal to stop worker 
    multiplayer.Q.put(None)

# Construct API
tvquiz_api = to_fast_api(lifespan=lifespan)


# Multiplayer support

@tvquiz_api.websocket("/ws")
async def websocket_endpoint(
        client: WebSocket,
        multiplayer=Depends(to_multiplayer)
    ):
    await multiplayer.connect(client)
    def n_now():
        return f'Now {len(multiplayer.clients)} users'
    print(f'Opened socket. {n_now()}') 
    while True: 
        try:
            await multiplayer.use_message(
                client
            )
        except WebSocketDisconnect:
            await multiplayer.untrack_client(client)
            print(f"Disconnected. {n_now()}")
            break
        except ConnectionClosed:
            await multiplayer.untrack_client(client)
            print(f"Closed Connection. {n_now()}")
            break
        except asyncio.CancelledError:
            await multiplayer.untrack_client(client)
            print(f"Cancelled Error. {n_now()}")
            break

'''
Constants
'''

@tvquiz_api.get("/api/latest_metadata")
def get_latest_metadata(
        config=Depends(to_config)
    ):
    return {
        'defaults': {
            'max_gen': config.default_max_gen,
        }
    }


@tvquiz_api.get("/api/valid_combos")
def get_valid_combos(
        config=Depends(to_config),
        max_gen: int | None = None
    ):
    gens = config.generations
    combos = config.valid_combos[(
        max_gen if max_gen in gens else max(gens)
    )]
    return [
        { 'combo': combo } for combo in combos 
    ]


'''
Pokemon forms and search
'''

@tvquiz_api.get("/api/forms")
def get_forms(
        config=Depends(to_config),
        dexn: int | None = None,
        max_gen: int | None = None
    ):
    if not dexn:
        return []
    _, forms = to_service(config).get_forms(dexn, max_gen)
    return forms

@tvquiz_api.get("/api/matches")
def get_matches(
        config=Depends(to_config), guess: str = '',
        max_gen: int | None = None
    ):
    gens = config.generations
    if max_gen not in gens:
        max_gen = max(gens)
    return to_service(config).get_matches(guess, max_gen)

'''
Validate guess on specific form
'''

@tvquiz_api.get("/api/test")
def run_test(
        config=Depends(to_config),
        form_id: int | None = None,
        conditions: str = ''
    ):
    # Comparison against conditions
    def str_cmp(x,y):
        return x.lower() == y.lower()
    fns = [
        (s, lambda x,arr: any(str_cmp(x,y) for y in arr))
        for s in conditions.split(',')
    ]
    return to_service(config).run_test(form_id, fns)
