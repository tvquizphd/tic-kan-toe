from util import set_config 
from util import describe_mon
from util import describe_type_combos
from util import read_extra_form_names
from util import read_type_combos
from util import read_game_list
from util import read_mon_list
from argparse import ArgumentParser
from api.service import Service 
from models import to_dex_map
from pathlib import Path

import requests
import asyncio
import uvicorn
import signal
import sys
import ssl

PORTS = {
    "client": 3134,
    "api": 3134 + 1
}

API_PORT = PORTS['api']
CLIENT_PORT = PORTS['client']
CERT_ROOT = Path('/etc/letsencrypt/live/')

parser = ArgumentParser(
                    prog='Tic Kan Toe API',
                    description='Test of Tic Kan Toe API',
                    epilog=f'Using the PokéAPI')
parser.add_argument('--cert-name', type=str)

def to_server(pem_path, port, module, scope, log_level):
    uvicorn_config = {
        "port": port,
        "reload": True,
        "host": "0.0.0.0",
        "log_level": log_level,
        "app": f"{module}:{scope}_{module}"
    }
    # Set up TLS
    has_certs = False
    if pem_path:
        ssl_keyfile = pem_path / 'privkey.pem'
        ssl_certfile = pem_path / 'cert.pem'
        has_certs = (
            ssl_keyfile.exists() and ssl_certfile.exists()
        )
    if has_certs:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(
            ssl_certfile, keyfile=ssl_keyfile
        )
        uvicorn_config["ssl_keyfile"] = ssl_keyfile
        uvicorn_config["ssl_certfile"] = ssl_certfile
    elif pem_path:
        print(f'Warning: missing files in {pem_path}')
    # Run with or without TLS
    config = uvicorn.Config(**uvicorn_config)
    return uvicorn.Server(config)


async def run_server(server):
    await server.serve()


async def run_tasks(pem_path):

    loop = asyncio.get_event_loop()
    api_server = to_server(
        pem_path, API_PORT, 'api', 'pd', 'info'
    )
    client_server = to_server(
        pem_path, CLIENT_PORT, 'client', 'pd', 'error'
    )
    api_task = asyncio.ensure_future(run_server(api_server))
    client_task = asyncio.ensure_future(run_server(client_server))

    # Consider following updates here:
    # https://github.com/encode/uvicorn/pull/1600
    tasks = [api_task, client_task]
    for job in asyncio.as_completed(tasks):
        try: 
            results = await job
        finally:
            break
            

def types_changed(old_type_combos, type_combos):
    return not all([
        tuple(old_type) == tuple(new_type)
        for old_type, new_type
        in zip(old_type_combos, type_combos)
    ]) and len(old_type_combos)

if __name__ == "__main__":

    api_url = 'https://pokeapi.co/api/v2/'

    print('Updating Games...', flush=True, file=sys.stderr)
    game_list = Service.update_games(
        api_url, list(read_game_list())
    )
    old_type_combos = list(read_type_combos())
    type_combos = describe_type_combos(api_url)
    extra_form_names = list(read_extra_form_names())
    mon_list = list(read_mon_list())

    # Must clear all Pokémon if new type introduced
    if types_changed(old_type_combos, type_combos):
        print('Wow! Found new types!')
        mon_list = []
    args = parser.parse_args()
    pem_path = (
        CERT_ROOT / args.cert_name
        if args.cert_name else None
    )

    print('Updating Pokémon...', flush=True, file=sys.stderr)
    dex_map = to_dex_map(game_list)
    # Load Pokémon
    while True:
        try:
            dexn = len(mon_list) + 1
            name, mon, extra_forms = (
                describe_mon(dexn, dex_map, type_combos, api_url,todo=True)
            )
            mon_list.append(mon)
            extra_form_names += extra_forms
            print(f'New: Pokémon #{dexn} {name}')
            if not len(extra_forms): continue
            print(
                ', '.join([f[1] for f in extra_forms[:2]]),
                '...' if len(extra_forms) > 2 else ''
            )
        except ValueError:
            break

    # Full range of the generations
    default_max_gen = 1
    set_config(**{
        'ports': PORTS, 'api_url': api_url,
        'default_max_gen': default_max_gen,
        'game_list': game_list, 'mon_list': mon_list,
        'extra_form_names': extra_form_names,
        'type_combos': type_combos,
    })

    # Test the API
    asyncio.run(run_tasks(pem_path))
