import timelineCSS from 'timeline-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { toTag, CustomTag } from 'tag';
import { getForms } from 'api';

const toTimelineModal = (data, actions) => {

  class TimelineModal extends CustomTag {

    static get setup() {
      return {
        updating_search: false,
        max_gen: data.max_gen,
      };
    }

    get root() {
      const to_gen_opts = () => {
        const gens = data.gen_years.map((gen) => {
          const valid = gen.n <= this.data.max_gen;
          return { n: gen.n, valid };
        });
        return gens.map((opt) => {
          const valid_class = () => {
            return ['valid',''][+!opt.valid];
          }
          const art_root = 'https://www.serebii.net/pokemon/generation';
          const png = toTag('div')``({
            'style': `
              background-image: url(${art_root+opt.n}.png);
            `,
            'class': 'png'
          });
          const button = toTag('div')`Gen ${opt.n}`({
            'class': 'button'
          });
          return toTag('div')`${png}${button}`({
            '@click': () => {
              data.resetRevive(opt.n);
              data.modal = null;
            },
            'class': valid_class 
          });
        });
      }

      const grid = toTag('div')`${to_gen_opts}`({
        'class': 'timeline-grid centered'
      });
      const label = 'Your most recent Pokémon games?'

      const center = toTag('div')`<h3>${label}</h3>${grid}`({
        class: 'center',
        '@click': (e) => {
          e.stopPropagation();
        }
      });

      return toTag('div')`
        ${center}`({
        class: () => {
          if (data.modal == 'timeline') {
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
      return [globalCSS, timelineCSS, sheet];
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

  return toTag('timeline', TimelineModal)``({
    max_gen: () => data.max_gen,
    class: 'parent modal'
  });

}

export { toTimelineModal };
