import navCSS from 'nav-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { backPhase, isFirstPhase } from 'phases';
import { nextPhase, isLastPhase } from 'phases';
import { toOnlineMenu } from 'online';
import { phaseMap } from 'phases';
import { toTag, CustomTag } from 'tag';

const toNav = (data) => {

  const colors = [
    [
      '--main-background', '--dark-text-color',
      '--the-box-shadow', '--main-text-shadow',
      'pointer'
    ],
    [
      '--error-background', '--error-text-color',
      '--error-box-shadow', '--error-text-shadow',
      'default'
    ]
  ];

  const online_menu = toOnlineMenu(data, globalCSS);

  class Nav extends CustomTag {

    static get setup() {
      return {
        tries: data.tries,
        max_tries: data.max_tries,
        text: '', err: data.err,
        max_gen: data.online.max_gen
      };
    }

    get need_reset() {
      return data.tries >= data.max_tries;
    }

    get root() {
      const reset_class = () => {
        return 'reset button' + [
          '', ' highlight'
        ][+this.need_reset];
      }
      const reset = toTag('div')`
      <img src="data/egg.png">
      </img><div>Reset</div>`({
          class: reset_class,
          '@click': () => {
            data.resetRevive();
          }
      });
      const header = () => {
        return toTag('div')`${d => d.text}`({
          class: 'centered-content main-title',
          data: this.data
        });
      }
      const to_years = () => {
        const start_end = data.gen_years.filter(gen => {
          return gen.n <= this.data.max_gen;
        });
        const splice_args = [
          1, start_end.length-2
        ];
        // Add the ellipsis
        if (start_end.length > 1) {
          splice_args.push({});
        }
        [].splice.apply(start_end, splice_args);
        return start_end.map((gen) => {
          if (!gen.year || !gen.n) {
            return toTag('div')`⋯`({
              'class': 'tall dots' 
            });
          }
          const art_root = 'https://www.serebii.net/pokemon/generation';
          return toTag('div')`${gen.year}`({
            'style': `
              background-image: url(${art_root+gen.n}.png);
            `,
            'class': 'tall' 
          });
        })
      }
      const dex_icon = toTag('img')``({
        'src': `data/dex.png`
      });
      const options = toTag('div')`${dex_icon}${to_years}`({
        class: 'full-content options-row button',
        '@click': () => {
          data.modal = 'timeline';
        }
      });
      const menu = toTag('div')`
      <img src="data/gb.svg">
      </img>`({
          class: 'menu icon',
          '@click': () => {
            data.ws_ping(true, 'hosting')
          }
      });
      const nav = toTag('div')`
        <div class="main-row full-content">
          ${reset}${header}${menu}
        </div> 
        ${options}
        ${online_menu}
      `({
        class: 'nav centered grid-row1'
      });
      // indicator
      const _indicator = (() => {
        const to_indicator = (i) => {
          const status_class = (prefix='') => {
            return prefix + [
              '', [' good', ' bad'][+(
                data.failures.includes(i)
              )]
            ][+(i <= data.tries)];
          }
          const blur_button = toTag('div')``({
            class: () => status_class('blur')
          });
          const num_button = toTag('div')`${i}`({
            class: () => status_class('')
          });
          return toTag('div')`${blur_button}${num_button}`();
        }
        const all_n = () => {
          return [
            ...Array(data.max_tries+1).keys()
          ].slice(1)
        };
        const evens = () => {
          const even_n = () => all_n().filter(n => n % 2 == 0);
          const evens = () => even_n().map(to_indicator);
          const front_style = () => {
            const n = all_n().length;
            return {
              2: 'width: 160px',
              4: 'width: 300px'
            }[evens().length] || '';
          }
          return toTag('div')`${evens}`({
            class: 'front',
            style: front_style
          })
        }
        const odds = () => {
          const odd_n = () => all_n().filter(n => n % 2 == 1);
          const odds = () => odd_n().map(to_indicator);
          const back_style = () => {
            const n = all_n().length;
            return {
              3: 'width: 260px',
              5: 'width: 300px'
            }[odds().length] || '';
          }
          return toTag('div')`${odds}`({
            class: 'back',
            style: back_style
          })
        }
        return  [
          odds, evens
        ];
      })();
      const buttons = toTag('div')`${_indicator}`({
        class: 'footer grid-row3'
      });
      return toTag('div')`${nav}${buttons}`({
        class: 'content'
      });
    }

    get styles() {
      const i = data.err % colors.length;
      const [
        background, color, shadow, text_shadow, cursor
      ] = colors[i];
      const sheet = new CSSStyleSheet();
      const last = isLastPhase(data.phase);
      sheet.replaceSync(`
      .nav {
        background-color: var(${background});
        text-shadow: var(${text_shadow});
        box-shadow: var(${shadow});
        color: var(${color});
        cursor: ${cursor};
      }`);
      return [globalCSS, navCSS, sheet];
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

  return toTag('nav', Nav)``({
    class: 'content',
    err: () => data.err,
    tries: () => data.tries,
    max_tries: () => data.max_tries,
    max_gen: () => data.online.max_gen,
    text: () => {
      return [
        'Tic Kan Toe',
        'Good Job!'
      ][data.phase];
    },
    data 
  });
}

export { toNav };
