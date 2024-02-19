import backdropCSS from 'backdrop-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { phaseMap, isPhase, nPhases } from 'phases';
import { 
  testGuess, getMatches, getRegions,
  getValidCombos, getLatestMetadata
} from 'api';
import { reactive } from '@arrow-js/core';
import { toBackdrop } from 'backdrop';
import { toPokemonGrid } from 'grid';
import { toSearchModal } from 'search';
import { toTimelineModal } from 'timeline';
import { 
  badge_info, to_random_badge,
  to_min_gym_badge,
  to_max_gym_badge 
} from 'badges';
import { toNav } from 'nav';
import { toTag } from 'tag';

const phase_list = [...Array(nPhases).keys()];

const HISTORY = 'conditions'
const MEMORY = [
  'online', 'failures', 'tries',
  'pokemon', 'rows', 'cols'
]

// Choose 6 random types
const randomConditions = async (api_root, max_gen=null) => {
  const grid_combos = (await getValidCombos(
    api_root, max_gen
  ));
  const grid_pairs = grid_combos.concat(
    grid_combos.map(c => [...c].reverse())
  );
  const banned_k = `tkt-saved-${HISTORY}`;
  const banned = JSON.parse(
    localStorage[banned_k] || "[]"
  ).map(xy => new Set(xy))
  const is_pair_found = (pair, list) => {
    // Pair matches some x in the list
    return list.some(x => x[0] == pair[0] && x[1] == pair[1]);
  }
  const is_set_found = (set, list, fn) => {
    // Set has some/every item from some x in the list
    return list.some(x => [...x][fn](xx => set.has(xx)));
  }
  const conditions = grid_pairs.filter(t => {
    return !is_set_found(new Set(t), banned, 'every');
  });
  const choice = (list) => {
    return list[Math.floor(Math.random() * list.length)];
  }
  const limit = 1000;
  let diagonals = []
  for (let i = 0; i <= limit; i++) {
    // Diagonals on matrix
    diagonals = ['','',''].reduce(({ins, outs}) => {
      // Indicate failure
      if (i != limit && ins.length == 0) {
        return { ins: [], outs: [] };
      }
      // Give up, provide unknown values
      let new_out = ['unknown', 'unknown'];
      // Usually there are items in ins
      if (ins.length > 0) {
        new_out = [...choice(ins)];
      }
      const new_outs = [...outs, new_out];
      const existing = new_outs.reduce((o0,n0) => {
        return [...o0, ...new_outs.reduce((o1,n1) => {
          return [...o1, [n0[0],n1[1]]];
        }, [])];
      }, []);
      const new_ins = ins.filter(pair => {
        // Prevent duplicates of existing entries
        return !is_set_found(new Set(pair), existing, 'some');
      }).filter(pair => {
        // Eliminate diagonals with invalid rows/columns 
        return new_outs.every(out => {
          return [
            is_pair_found([pair[0], out[1]], conditions),
            is_pair_found([out[0], pair[1]], conditions)
          ].every(x => x);
        });
      })
      return { ins: new_ins, outs: new_outs };
    }, { ins: [...conditions], outs: []}).outs;
    // Found valid diagonals
    if (diagonals.length == 3) break;
  }
  // All available types
  return [
    diagonals[0][0], diagonals[1][0], diagonals[2][0],
    diagonals[0][1], diagonals[1][1], diagonals[2][1]
  ]
}

const forget = (memory) => {
  memory.forEach(label => {
    const k = `tkt-saved-${label}`;
    return localStorage.removeItem(k);
  });
}

const remember = (opts, ws_send, action=null) => {
  const no_json = ['tries'];
  MEMORY.forEach(label => {
    const val = opts[label];
    if (!val) return;
    const k = `tkt-saved-${label}`;
    if (no_json.includes(label)) {
      return localStorage.setItem(k, `${val}`);
    }
    localStorage.setItem(k, JSON.stringify(val));
  });
  ws_send(opts, action);
}

const to_saved_state = () => {
  const found = MEMORY.map(label => {
    const k = `tkt-saved-${label}`
    return localStorage.getItem(k);
  });
  const [
    online, failures, tries,
    pokemon, rows, cols
  ] = found;
  const saved = found.every(x => x !== null);
  return {
    saved,
    tries: parseInt(tries || 0),
    failures: JSON.parse(failures), 
    pokemon: JSON.parse(pokemon),
    online: JSON.parse(online),
    rows: JSON.parse(rows),
    cols: JSON.parse(cols)
  };
}

const offer_new_badge = (offer, max_gen) => {
  const badge_offer = offer || (
    to_random_badge(max_gen)
  );
  // Badge at or below max gen 
  return 1 + (
    (badge_offer - 1)
  % to_max_gym_badge(
    max_gen
  ));
}

const to_ws_message = (
  online, ws_state, opts
) => {
  const { cols, rows, contents } = opts;
  const message = {
    ...online, ws_state,
    grid_state: {
      contents, cols, rows
    },
  }
  if (opts.action) {
    const { content, position } = opts.action;
    message.grid_action = { content, position };
  }
  return JSON.stringify(message);
}

const update_online = (online, offer, ws_send) => {
  const badge_offer = offer_new_badge(
    offer, online.max_gen
  );
  const new_online = {
    ...online, badge_offer 
  }
  // Save to URL and Cache
  write_hash(new_online.max_gen);
  remember({ online: new_online }, ws_send);
  return new_online; 
}

const verify_online = (online, ws_send) => {
  return update_online(
    online, online.badge_offer, ws_send
  );
}

const create_online = (online, opts, ws_send) => {
  const user_id = crypto.randomUUID();
  return verify_online({
    ...online, ...opts,
    user_id, is_on: false,
    group_ids: [ user_id ]
  }, ws_send);
}

const has_failed = (failures, tries, max_tries) => {
  return failures.length && tries >= max_tries;
}

const read_hash = (server_meta) => {
  const args = window.location.hash.slice(1).split('/');
  const [max_gen] = args;
  return {
    max_gen: parseInt(max_gen) || server_meta.max_gen
  }
}

const write_hash = (...args) => {
  window.location.hash = args.join('/');
}

const initialize = async (api_root, ws_send, details={}) => {

  const saved = to_saved_state();
  const wiki = 'query.wikidata.org';
  const num_details = Object.keys(details).length;
  const server_meta = await getLatestMetadata(
    api_root, wiki
  );
  const { gen_years } = server_meta;
  if (saved.saved && num_details == 0) {
    const {
      failures,
      tries, pokemon, rows, cols
    } = saved;
    const online = verify_online(
      {
        ...saved.online, is_on: false,
      }, ws_send
    );
    const memory = { 
      gen_years,
      online, failures,
      tries, pokemon, rows, cols
    };
    remember(memory, ws_send);
    return memory;
  }
  const pokemon = [
    0,1,2,3,4,5,6,7,8
  ].map(() => {
    return null; 
  });
  // Fallback to hash or server metadata 
  const hash_values = read_hash(server_meta);
  const online_opts = {
    max_gen: hash_values.max_gen
  }
  // Prefer to take values from details
  const options = ['max_gen', 'badge_offer'];
  options.forEach((k) => {
    if (!details[k]) return;
    online_opts[k] = details[k];
  });
  const rand = await randomConditions(
    api_root, online_opts.max_gen 
  );
  const cols = [0,1,2].map(i => rand[i]);
  const rows = [3,4,5].map(i => rand[i]);
  // Prevent choices from being selected next time
  const conditions = rows.reduce((x,r) => {
    return cols.reduce((y,c) => ([...y, [r,c]]), x);
  }, []);
  forget(MEMORY);
  const online = create_online(
    (saved.online || {}), online_opts, ws_send
  );
  const memory = {
    online, failures: [], tries: 0,
    pokemon, rows, cols,
    gen_years,
  }
  // Remember new initialization
  remember(memory, ws_send);
  return memory;
}

const main = async (api_port) => {
  const host = window.location.hostname;
  const api_root = `https://${host}:${api_port}`;
  const ws_url = `wss://${host}:${api_port}/ws`;
  let ws = new WebSocket(ws_url);
  const no_send = () => null;
  const no_matches = [];
  const {
    gen_years,
    online, failures,
    tries, pokemon, rows, cols
  } = await initialize(api_root, no_send);
  // Remember new initialization
  remember({
    online, failures, tries,
    pokemon, rows, cols
  }, no_send);
  const github_root = 'https://raw.githubusercontent.com/PokeAPI/sprites/master';
  const data = reactive({
    online,
    phaseMap,
    tries: tries,
    modal: null,
    content: '',
    cols, rows,
    gen_years,
    failures: failures,
    phase: 0, active_square: 0,
    max_tries: 9,
    err: has_failed(failures, tries, 9),
    pokemon: pokemon,
    matches: no_matches,
    github_root: github_root,
    ws_state: 'quitter',
    set_max_tries: (is_on) => {
      data.max_tries = [9, 5][+is_on];
      data.tries = Math.min(
        data.max_tries, data.tries
      );
      data.failures = [];
    },
    ws_ping: (is_on, ws_state) => {
      // Reopen the websocket
      if (ws.readyState === WebSocket.CLOSED) {
        ws = new WebSocket(ws_url);
      }
      const updated = [
        data.ws_state != ws_state,
        data.online.is_on != is_on
      ].some(x => x)
      data.online.is_on = is_on;
      data.set_max_tries(is_on); 
      data.ws_state = ws_state;
      if (updated) {
        remember(data, data.ws_send);
      };
    },
    ws_send: (opts, action=null) => {
      if (!data.online.is_on) return;
      ws.send(data.to_message(
        opts, action
      ));
    },
    to_message: (opts, action=null) => {
      const online = {
        ...data.online, ...(opts.online || {})
      };
      const contents = (
        opts.pokemon || data.pokemon
      );
      const rows = opts.rows || data.rows;
      const cols = opts.cols || data.cols;
      /* TODO
       * opts.failures / opts.tries
       */
      return to_ws_message(
        online, data.ws_state, {
          contents, action, rows, cols
        }
      )
    },
    resetRevive: async (_max_gen=null) => {
      if (data.ws_state == 'found') {
        return; // No resetting in battle
      }
      const badge = data.online.badge_offer;
      // Find a new badge within the new gen
      const reset_badge = _max_gen && (
        to_max_gym_badge(_max_gen) < badge
        || badge < to_min_gym_badge(_max_gen)
      );
      if (_max_gen) {
        data.online.max_gen = _max_gen;
      }
      const {
        gen_years,
        online, failures,
        tries, pokemon, rows, cols
      } = await initialize(api_root, data.ws_send, {
        max_gen: data.online.max_gen,
        badge_offer: reset_badge ? (
          to_random_badge(_max_gen)
        ) : null
      });
      const { max_tries } = data;
      data.err = has_failed(failures, tries, max_tries);
      data.failures = failures;
      data.pokemon = pokemon;
      data.online = online;
      data.tries = tries;
      data.rows = rows;
      data.cols = cols;
    },
    closeModal: () => {
      data.modal = null;
    },
    toFormPngUrl: (id) => {
      const repo = 'https://raw.githubusercontent.com/PokeAPI/sprites';
      return `${repo}/master/sprites/pokemon/other/official-artwork//${id}.png`;
    },
    offerNewBadge: (offer) => {
      data.online = update_online(
        data.online, offer, data.ws_send
      );
    },
    toMatches: async (guess, max_gen) => {
      const root = data.api_root;
      const matches = getMatches(root, guess, max_gen);
      return await matches;
    },
    testGuess: async (mon) => {
      const col = data.active_square % 3; 
      const row = Math.floor(data.active_square / 3);
      const conditions = [
        data.cols[col], data.rows[row]
      ];
      // Show failure status
      if (data.tries < data.max_tries) {
        data.tries += 1;
      }
      const passed = await testGuess(
        data.api_root, mon.id, conditions
      );
      if (!passed) {
        data.failures.push(data.tries);
      }
      const failed_args = [
        data.failures, data.tries, data.max_tries
      ]
      if (has_failed(...failed_args)) {
        data.err = 1;
      }
      if (passed) {
        data.pokemon = data.selectPokemon(
          data.pokemon, mon
        );
      }
      else {
        data.selectPokemon(
          data.pokemon
        );
      }
      return passed;
    },
    selectPokemon: (mons, new_mon=null) => {
      const new_pokemon = mons.map((mon, i) => {
        if (new_mon == null) return mon;
        if (i != data.active_square) return mon;
        return new_mon;
      });
      const action = new_mon ? ({
        content: new_mon,
        position: data.active_square
      }): null;
      // Send Action
      remember({
        ...data, pokemon: new_pokemon
      }, data.ws_send, action);
      return new_pokemon;
    },
    api_root: api_root,
    width: window.innerWidth,
    height: window.innerHeight,
    skipInvalidPhase: (phase) => {
      return [ /* Phases to skip */ ].some(x => x);
    }
  });
  ws.onclose = () => {
    alert('game briefly unavailable');
  }
  ws.onmessage = (event) => {
    if (!data.online.is_on) return;
    const updates = JSON.parse(event.data);
    const {
      group_ids, max_gen, badge_offer, ws_state
    } = updates;
    if (!group_ids.includes(data.online.user_id)) {
      return;
    }
    // Mimic Server side logs
    const group_str = group_ids.map(v => `'${v}'`).join(', ');
    console.log(`From: (${group_str}) ${ws_state}`);
    const {
      contents, rows, cols
    } = updates.grid_state;
    // Update and cache data
    data.online = verify_online({
      ...data.online, max_gen, badge_offer,
      user_id: data.online.user_id
    }, no_send);
    data.online.is_on = updates.is_on
    data.set_max_tries(updates.is_on); 
    /* TODO does this make sense?
     * failures, tries
     */
    if (ws_state == 'found' && data.ws_state != 'found') {
      data.tries = contents.reduce((sum, v) => {
        return sum + +(v != null);
      }, 0)
      data.failures = []
    }
    data.ws_state = ws_state;
    data.pokemon = contents;
    data.rows = rows;
    data.cols = cols;
    remember(data, no_send);
  }
  window.addEventListener('resize', handleResize(data));
  document.adoptedStyleSheets = [
    globalCSS, backdropCSS
  ];
  // Main Content 
  const nav = toNav(data);
  const pokemonGrid = toPokemonGrid(data, globalCSS);
  const searchModal = toSearchModal(data, globalCSS);
  const timelineModal = toTimelineModal(data, globalCSS);
  // Animated Background
  const backdrop = toBackdrop(data);
  // Containers
  const centered = toTag('div')`
    ${nav}${pokemonGrid}
  `({
    class: 'centered root index'
  });
  return toTag('div')`
    ${backdrop}${centered}
    ${searchModal}${timelineModal}
  `({
    class: 'centered root wrapper',
  })(document.body);
}

const parseDate = (date_string) => {
  if (date_string === null) return null;
  return new Date(Date.parse(date_string));
}

const handleResize = (d) => {
  return () => {
    d.height = window.innerHeight;
    d.width = window.innerWidth;
  }
}

export default main
