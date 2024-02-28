from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY as _422
from starlette.status import HTTP_201_CREATED as _201
from fastapi.exceptions import RequestValidationError
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from fastapi.middleware.cors import CORSMiddleware
from concurrent.futures import ThreadPoolExecutor
from fastapi.responses import JSONResponse
from starlette.requests import Request
from fastapi import Depends, FastAPI, WebSocket
from contextlib import asynccontextmanager
from api.service import to_service
from util import to_multiplayer
from util import to_config
import asyncio
import json

@asynccontextmanager
async def lifespan(
    app: FastAPI
):
    # Initialize Multiplayer
    multiplayer = to_multiplayer()
    # Any startup costs before yield
    yield
    # Sentinal to stop Q worker 
    multiplayer.Q.put(None)
    print('API Server Shutdown Complete')
    # Any shutdown costs after yield

# Construct API
pd_api = FastAPI(lifespan=lifespan)
pd_api.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

pool = ThreadPoolExecutor(max_workers=1)

# Handle common FastAPI exceptions
@pd_api.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    content = {'status_code': 10422, 'data': None}
    print(f'{exc}'.replace('\n', ' ').replace('   ', ' '))
    return JSONResponse(content=content, status_code=_422)

'''
TODO: Documentation for Development
'''

@pd_api.get("/api")
def open_root_api(config=Depends(to_config)):
    return { **vars(config) }


# Multiplayer support

@pd_api.websocket("/ws")
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

@pd_api.get("/api/latest_metadata")
def get_latest_metadata(
        config=Depends(to_config),
        max_gen: int | None = None
    ):
    return {
        'defaults': {
            'max_gen': config.default_max_gen,
        }
    }


@pd_api.get("/api/valid_combos")
def get_valid_combos(
        config=Depends(to_config),
        max_gen: int | None = None
    ):
    max_max = max(config.generations)
    max_gen = min(
        max_gen or max_max, max_max
    )
    valid_combos = config.valid_combos[max_gen]
    return [
        { 'combo': combo }
        for combo in valid_combos
    ]


'''
Pokemon forms and search
'''

@pd_api.get("/api/forms")
def get_forms(
        config=Depends(to_config), dexn: str = ''
    ):
    return to_service(config).get_forms(dexn)

@pd_api.get("/api/matches")
def get_matches(
        config=Depends(to_config), guess: str = '',
        max_gen: int | None = None
    ):
    max_max = max(config.generations)
    max_gen = min(
        max_gen or max_max, max_max
    )
    return to_service(config).get_matches(guess, max_gen)

'''
Validate guess
'''

@pd_api.get("/api/test")
def run_test(
        config=Depends(to_config),
        identifier: str = '',
        conditions: str = ''
    ):
    # Comparison against conditions
    str_cmp = lambda x, y: x.lower() == y.lower()
    fns = [
        (s, lambda x,arr: any([str_cmp(x,y) for y in arr]))
        for s in conditions.split(',')
    ]
    return to_service(config).run_test(identifier, fns)
