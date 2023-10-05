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
import { toNav } from 'nav';
import { toTag } from 'tag';

const phase_list = [...Array(nPhases).keys()];

// Choose 6 random types
const randomConditions = async (api_root, max_gen=null) => {
  const grid_combos = (await getValidCombos(
    api_root, max_gen
  ));
  const grid_pairs = grid_combos.concat(
    grid_combos.map(c => [...c].reverse())
  );
  const banned = JSON.parse(
    localStorage['tkt-saved-conditions'] || "[]"
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

const remember = (new_pokemon, failures, max_gen, tries) => {
  // Prevent choices from being selected next time
  localStorage.setItem("tkt-saved-tries", `${tries}`);
  localStorage.setItem("tkt-saved-max_gen", `${max_gen}`);
  localStorage.setItem("tkt-saved-failures", JSON.stringify(
    failures
  ));
  localStorage.setItem("tkt-saved-pokemon", JSON.stringify(
    new_pokemon
  ));
}

const has_saved_state = () => {
  const found = [
    'failures', 'max_gen', 'tries', 'pokemon', 'rows', 'cols'
  ].map(k => {
    return localStorage.getItem(`tkt-saved-${k}`);
  });
  const [failures, max_gen, tries, pokemon, rows, cols] = found;
  const saved = found.every(x => x !== null);
  return [
    saved, JSON.parse(failures), parseInt(max_gen || 1),
    parseInt(tries || 0), pokemon, rows, cols
  ];
}

const has_failed = (failures, tries) => {
  return failures.length && tries >= 9;
}

const read_hash = (server_meta) => {
  const args = window.location.hash.slice(1).split('/');
  const [max_gen] = args;
  return {
    max_gen: parseInt(max_gen) || server_meta.max_gen
  }
}

const write_hash = (max_gen) => {
  window.location.hash = `${max_gen}/`;
}

const initialize = async (api_root, details={}) => {

  const saved = has_saved_state();
  const wiki = 'query.wikidata.org';
  const num_details = Object.keys(details).length;
  const server_meta = await getLatestMetadata(
    api_root, wiki
  );
  const { gen_years } = server_meta;
  if (saved[0] && num_details == 0) {
    const saved_state = saved.slice(1);
    const [
      failures, max_gen, tries, pokemon, rows, cols
    ] = saved_state;
    write_hash(max_gen);
    return { 
      tries, pokemon, rows, cols, max_gen, gen_years,
      failures
    };
  }
  const pokemon = JSON.stringify([
    0,1,2,3,4,5,6,7,8
  ].map(() => {
    return null; 
  }));

  // 1) argument, 2) hash, 3) server_meta
  const max_gen = details.max_gen || (
    read_hash(server_meta).max_gen
  );
  const rand = await randomConditions(
    api_root, max_gen 
  );
  const col_list = [0,1,2].map(i => rand[i]);
  const row_list = [3,4,5].map(i => rand[i]);
  const cols = JSON.stringify(col_list);
  const rows = JSON.stringify(row_list);

  // Prevent choices from being selected next time
  localStorage.removeItem("tkt-saved-tries");
  localStorage.removeItem("tkt-saved-max_gen");
  localStorage.removeItem("tkt-saved-failures");
  localStorage.removeItem("tkt-saved-pokemon");
  localStorage.setItem("tkt-saved-rows", rows);
  localStorage.setItem("tkt-saved-cols", cols);
  localStorage.setItem("tkt-saved-conditions", JSON.stringify(
    row_list.reduce((x,r) => {
      return col_list.reduce((y,c) => ([...y, [r,c]]), x);
    }, [])
  ));
  write_hash(max_gen);
  return {
    tries: 0, pokemon, rows, cols, max_gen, gen_years,
    failures: []
  };
}

const main = async () => {
  
  const host = window.location.hostname;
  const api_root = `http://${host}:3135`;
  const no_matches = JSON.stringify([]);
  const {
    tries, rows, cols, pokemon,
    max_gen, gen_years, failures 
  } = await initialize(api_root);
  const github_root = 'https://raw.githubusercontent.com/PokeAPI/sprites/master';
  const data = reactive({
    phaseMap,
    tries: tries,
    modal: null,
    content: '',
    cols, rows,
    failures: failures,
    gen_years, max_gen,
    phase: 0, active_square: 0,
    err: has_failed(failures, tries),
    pokemon: pokemon,
    matches: no_matches,
    github_root: github_root,
    resetRevive: async (_max_gen=null) => {
      if (_max_gen) data.max_gen = _max_gen;
      const {
        tries, rows, cols, pokemon,
        max_gen, gen_years, failures
      } = await initialize(api_root, {
        max_gen: data.max_gen
      });
      data.err = has_failed(failures, tries),
      data.failures = failures;
      data.pokemon = pokemon;
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
    toMatches: async (guess, max_gen) => {
      const root = data.api_root;
      const matches = getMatches(root, guess, max_gen);
      return await matches;
    },
    testGuess: async (id) => {
      const col = data.active_square % 3; 
      const row = Math.floor(data.active_square / 3);
      const conditions = [
        JSON.parse(data.cols)[col], JSON.parse(data.rows)[row]
      ];
      // Show failure status
      if (data.tries < 9) data.tries += 1;
      const passed = await testGuess(
        data.api_root, id, conditions
      );
      if (!passed) {
        data.failures.push(data.tries);
      }
      if (has_failed(data.failures, data.tries)) {
        data.err = 1;
      }
      return passed;
    },
    selectPokemon: (mons, new_mon=null) => {
      const new_pokemon = mons.map((mon, i) => {
        if (new_mon == null) return mon;
        if (i != data.active_square) return mon;
        return new_mon;
      });
      remember(new_pokemon, data.failures, data.max_gen, data.tries);
      return new_pokemon;
    },
    api_root: api_root,
    width: window.innerWidth,
    height: window.innerHeight,
    skipInvalidPhase: (phase) => {
      return [ /* Phases to skip */ ].some(x => x);
    }
  });
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
    ${backdrop}
    ${searchModal}${timelineModal}
    ${centered}
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
