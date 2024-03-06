import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from starlette.status import (
    HTTP_201_CREATED as _201,
    HTTP_422_UNPROCESSABLE_ENTITY as _422
)
from starlette.requests import Request
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import JSONResponse
from api.service import to_service
from util import to_multiplayer
from util import to_config

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
tvquiz_api = FastAPI(lifespan=lifespan)
tvquiz_api.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

pool = ThreadPoolExecutor(max_workers=1)

# Handle common FastAPI exceptions
@tvquiz_api.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    content = {'status_code': 10422, 'data': None}
    print(f'{exc}'.replace('\n', ' ').replace('   ', ' '))
    return JSONResponse(content=content, status_code=_422)

'''
TODO: Documentation for Development
'''

@tvquiz_api.get("/api")
def open_root_api(config=Depends(to_config)):
    return { **vars(config) }


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
