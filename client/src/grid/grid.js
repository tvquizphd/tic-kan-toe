import pokemonGridCSS from 'grid-css' assert { type: 'css' };
import { toTag, CustomTag } from 'tag';
import { phases, phaseMap, isPhase } from 'phases';

const toPokemonSprite = (err, no_mon, png_url) => {
  if (no_mon() && err) return null;
  return toTag('img')``({
    class: () => {
      if (no_mon()) return 'full placeholder';
      return 'full';
    },
    src: () => {
      return no_mon() ? '' : png_url();
    }
  });
}

function* addHeaders (squares, data) {
  yield toTag('div')``({
    class: 'corner header'
  });

  const mod = data.rows.length;
  for (let c = 0; c < mod; c++) {
      const to_c = () => data.cols[c];
      yield toTag('div')`
      <div class="${to_c}">${to_c}</div>
      `({
        class: 'column header'
      });
  }
  for (let sq = 0; sq < mod*mod; sq++) {
    const square = squares[sq];
    const r = Math.floor(sq / mod);
    const to_r = () => data.rows[r];
    if (sq % mod == 0) {
      yield toTag('div')`
      <div class="${to_r}">${to_r}</div>
      `({
        class: 'row header'
      });
    }
    yield square;
  }
}

const toPokemonGrid = (data, globalCSS) => {

  class PokemonGrid extends CustomTag {

    static get setup() {
      return {
        cols: JSON.stringify(data.cols),
        rows: JSON.stringify(data.rows),
        pokemon: JSON.stringify(data.pokemon)
      };
    }

    get root() {
      const mons = [0,1,2,3,4,5,6,7,8].map((i) => {
        return () => data.pokemon[i];
      });
      const squares = mons.map((to_mon, i) => () => {
        const no_mon = () => to_mon() == null;
        const to_id = () => to_mon()?.id;
        const to_name = () => to_mon()?.name;
        const to_gen = () => {
          const gen = to_mon()?.generation
          return `Gen ${parseInt(gen) || '?'}`;
        }
        const png_url = () => data.toFormPngUrl(to_id())
        const to_pokemon = () => {
          const pokemon = toPokemonSprite(
            data.err, no_mon, png_url
          );
          if (pokemon) {
            return pokemon;
          }
          const egg_style = () => {
            if (data.online.is_on) {
              return ''; // No rest if online 
            }
            return `background-image: url(${data.github_root}/sprites/items/mystery-egg.png)`;
          }
          return toTag('div')``({
              style: egg_style,
              class: 'centered full placeholder error'
          });
        }
        const prob = toTag('div')`${
          () => no_mon()? '' : to_gen()
        }`({
          class: 'top right'
        });
        const name = toTag('div')`${
          () => to_name() || ''
        }`({
          class: 'bottom full'
        })
        return toTag('div')`
          ${to_pokemon}${prob}${name}
        `({
          '@click': () => {
            if (data.err) {
              data.resetRevive();
              return;
            }
            if (!no_mon()) return;
            data.active_square = i;
            data.modal = 'search';
            // Prepare Autofocus
            const search = document.querySelector('tkt-search').shadowRoot;
            const input = search.querySelector('input[autofocus]');
            input.focus();
          }
        });
      });

      const items = [...addHeaders(squares, data)];

      return toTag('div')`${items}`({
        'class': 'pokemon-grid centered'
      });
    }

    get styles() {
      return [globalCSS, pokemonGridCSS];
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

  return toTag('pokemon-grid', PokemonGrid)``({
    pokemon: () => JSON.stringify(data.pokemon),
    rows: () => JSON.stringify(data.rows),
    cols: () => JSON.stringify(data.cols),
    class: 'grid-row2'
  });
}

export { toPokemonGrid };
