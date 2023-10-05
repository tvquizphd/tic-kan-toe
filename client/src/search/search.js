import searchCSS from 'search-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { toTag, CustomTag } from 'tag';
import { getForms } from 'api';

class SearchQueue {

  constructor() {
    this.reset();
    this._cache = {};
    this.queue_reading();
  }

  reset () {
    this.queue = [];
  }

  needs (purpose, key) {
    const pending = this.pending(purpose);
    const not_pending = !pending.includes(key);
    const not_cached = !this.cached(purpose, key);
    return not_pending && not_cached;
  }

  cache (purpose, key, value) {
    const cache = this._cache[purpose] || new Map();
    cache.set(key, value);
    this._cache[purpose] = cache;
  }

  cached (purpose, key) {
    const cache = this._cache[purpose] || new Map();
    const found = cache.get(key);
    if (found) return found;
    return null; 
  }

  set latest (latest) {
    this.queue.unshift(latest);
  }

  get latest () {
    return this.queue.pop() || {
      data: {},
      purpose: null,
      fn: () => null,
    };
  }

  pending (purpose) {
    return this.queue.filter((q) => {
      return q.purpose === purpose;
    }).map((q) => {
      return q.data;
    });
  }

  async queue_reading() {
    const _time = await new Promise((resolve) => {
      // Execute the command
      this.latest.fn();
      // Wait for next command
      window.setTimeout(() => {
        window.requestAnimationFrame(resolve);
      }, 1000 / 5);
    });
    await this.queue_reading();
  }
}

const toSearchModal = (data, actions) => {

  const searchQueue = new SearchQueue();

  class SearchModal extends CustomTag {

    static get setup() {
      return {
        pokemon: JSON.parse(data.pokemon),
        matches: JSON.parse(data.matches),
        updating_search: false,
        max_gen: data.max_gen,
        search: '',
      };
    }

    get mons() {
      return [...this.data.matches].reduce((forms, p) => {
        if (searchQueue.needs('forms', p.dex)) {
          // Queue fetch for this form
          searchQueue.latest = {
            data: { ...p },
            purpose: 'forms',
            fn: this.fetchPokemonForms.bind(this, p.dex)
          };
          return forms;
        }
        else if (p.forms.length == 0) {
          // Use any cached forms if avilable
          p.forms = searchQueue.cached('forms', p.dex) || [];
        }
        return [
          ...forms, ...p.forms.map((f) => {
            const { name, generation, id } = f;
            return {
              name, generation, id, key: id
            };
          })
        ];
      }, []);
    }

    get root() {
      const to_accept = (mon) => {
        return toTag('div')`Guess`({
          class: 'accept',
          '@click': async () => {
            this.data.search = '';
            const ok = await data.testGuess(mon.id);
            if (ok) {
              data.pokemon = JSON.stringify(
                data.selectPokemon(
                  this.data.pokemon, mon
                )
              );
            }
            else {
              data.selectPokemon(
                this.data.pokemon
              );
            }
            data.closeModal(); 
          }
        });
      }
      const items = () => { 
        return this.mons.map((mon) => {
          const to_url = () => data.toFormPngUrl(mon.id);
          const no_form = () => mon.id === null;
          const img = toTag('img')``({
            src: () => {
              return no_form() ? '' : to_url();
            }
          });
          return toTag('div')`
            ${img}${mon.name}
            <div>${to_accept(mon)}</div>
          `({
            key: mon.key
          });
        });
      }
      const results = toTag('div')`${() => items()}`({
        class: 'results'
      });
      const search = toTag('input')``({
        value: () => this.data.search,
        placeholder: 'Search Pokémon...',
        '@input': (event) => {
          // stop searching for old data
          this.data.search = event.target.value;
          // Don't update if already updating
          if (this.data.updating_search) {
            return;
          }
          searchQueue.reset();
          this.data.updating_search = true;
          // Recursive update function
          const update_matches = () => {
            const guess = this.data.search;
            const max_gen = this.data.max_gen;
            data.toMatches(guess, max_gen).then((new_matches) => {
              data.matches = JSON.stringify(new_matches);
              const need_refresh = this.data.search != guess;
              this.data.updating_search = need_refresh;
              if (need_refresh) {
                update_matches();
              }
            });
          }
          update_matches();
        },
        autofocus: "",
        class: 'search',
        type: 'text'
      })
      const center = toTag('div')`
      ${search}${results}
      `({
        class: 'center',
        '@click': (e) => {
          e.stopPropagation();
        }
      });
      return toTag('div')`
        ${center}`({
        class: () => {
          if (data.modal == 'search') {
            return 'shown modal wrapper';
          }
          return 'hidden modal wrapper';
        },
        '@click': () => {
          data.closeModal();
        }
      });
    }

    get styles() {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(`
      .todo {
      }`);
      return [globalCSS, searchCSS, sheet];
    }

    async fetchPokemonForms(dexn) {
      if (searchQueue.needs('forms', dexn)) {
        // Request all regional forms for the pokemon
        const forms = await getForms(data.api_root, dexn);
        searchQueue.cache('forms', dexn, forms);
        this.data.matches = this.data.matches.map((p) => {
          if (p.dex == dexn) {
            p.forms = forms;
          }
          return p;
        });
      }
    }

    attributeChangedCallback(name, _, v) {
      let parsed = v;
      try {
        parsed = JSON.parse(v)
      } catch {
      }
      super.attributeChangedCallback(name, _, parsed);
    }
  }

  return toTag('search', SearchModal)``({
    pokemon: () => data.pokemon,
    matches: () => data.matches,
    max_gen: () => data.max_gen,
    class: 'parent modal',
    search: '',
  });

}

export { toSearchModal };
