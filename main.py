import sys
import ssl
import signal
from pathlib import Path
from argparse import ArgumentParser
import asyncio
import uvicorn
from util import (
    set_config, describe_mon, describe_type_combos,
    read_extra_form_name_dict, read_form_count_list,
    read_form_index_list, read_type_combos, read_game_list
)
from models import (
    unpackage_mon_list 
)
from api.service import Service 

CERT_ROOT = Path('/etc/letsencrypt/live/')

parser = ArgumentParser(
                    prog='Tic Kan Toe API',
                    description='Test of Tic Kan Toe API',
                    epilog='Using the PokéAPI')
parser.add_argument('--cert-name', type=str)
parser.add_argument('--ui-port', type=int, default=3134)
parser.add_argument('--default-max-gen', type=int, default=1)

def to_server(pem_path, port, module, scope, log_level):
    print(f'Running {scope} {module} on port {port}')
    uvicorn_config = {
        "port": port,
        "reload": False,
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
    # See https://github.com/encode/uvicorn/issues/1579#issuecomment-1604484876
    class Server(uvicorn.Server):
        def install_signal_handlers(self):
            pass
    return Server(config)


async def run_tasks(ports, pem_path):

    asyncio.get_event_loop()
    api_server = to_server(
        pem_path, ports['api'], 'api', 'tvquiz', 'info'
    )
    client_server = to_server(
        pem_path, ports['client'], 'client', 'tvquiz', 'error'
    )
    api_task = asyncio.ensure_future(api_server.serve())
    client_task = asyncio.ensure_future(client_server.serve())

    # Consider following updates here:
    # https://github.com/encode/uvicorn/pull/1600
    tasks = [api_task, client_task]
    def signal_handler(_s,_f):
        api_server.should_exit = True
        client_server.should_exit = True
    signal.signal(signal.SIGINT, signal_handler)
    await asyncio.gather(*tasks)
    print('\nClosed servers')    

def types_changed(old_type_combos, new_type_combos):
    return not all(
        tuple(old_type) == tuple(new_type)
        for old_type, new_type
        in zip(old_type_combos, new_type_combos)
    ) and len(old_type_combos)


def update_type_combos(api_url):
    old_type_combos = list(read_type_combos())
    new_type_combos = describe_type_combos(api_url)
    return new_type_combos, types_changed(
        old_type_combos, new_type_combos
    )

def start_servers(args, **config_kwargs):
    ports = {
        'client': args.ui_port,
        'api': args.ui_port + 1
    }
    pem_path = (
        CERT_ROOT / args.cert_name
        if args.cert_name else None
    )
    set_config(**{
        **config_kwargs, 'ports': ports,
        'default_max_gen': args.default_max_gen
    })
    asyncio.run(run_tasks(ports, pem_path))


def load_updates(api_url):
    extra_form_name_dict = read_extra_form_name_dict()
    type_combos, found_new_types = update_type_combos(api_url)
    # Must clear cache of all pokemon data if new types found
    mon_list = [] if found_new_types else list(unpackage_mon_list(
        list(read_form_count_list()),
        list(read_form_index_list()),
        extra_form_name_dict
    ))
    if found_new_types:
        print('Wow! Found new types!')

    print('Updating Games...', flush=True, file=sys.stderr)
    game_list = Service.update_games(
        api_url, list(read_game_list())
    )
    print('Updating Pokémon...', flush=True, file=sys.stderr)
    # Load Pokémon
    while True:
        try:
            dexn = len(mon_list) + 1
            name, mon, extra_forms = (
                describe_mon(dexn, type_combos, api_url)
            )
            mon_list.append(mon)
            print(f'Loaded Pokémon #{dexn} {name}')
            for form_id, name in extra_forms:
                extra_form_name_dict[form_id] = name
            if not len(extra_forms) > 0:
                continue
            print(
                'Forms:',
                ', '.join([f[1] for f in extra_forms[:2]]),
                '...' if len(extra_forms) > 2 else ''
            )
        except ValueError:
            break

    return {
        'extra_form_name_dict': extra_form_name_dict,
        'type_combos': type_combos,
        'game_list': game_list,
        'mon_list': mon_list
    }

if __name__ == "__main__":

    API_URL = 'https://pokeapi.co/api/v2/'
    updates = load_updates(API_URL)
    start_servers(
        parser.parse_args(),
        api_url = API_URL,
        extra_form_name_dict = updates['extra_form_name_dict'],
        type_combos = updates['type_combos'],
        game_list = updates['game_list'],
        mon_list = updates['mon_list'],
    )
