import onlineCSS from 'online-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { 
  badge_info, to_max_gym_badge
} from 'badges';
import { toTag, CustomTag } from 'tag';

const toOnlineMenu = (data, actions) => {

  class OnlineMenu extends CustomTag {

    static get setup() {
      this._timer = null;
      return {
        max_gen: data.online.max_gen,
        is_on: data.online.is_on,
        finding: false,
        found: false,
        badge_y: 0
      };
    }

    get root() {
      const disconnect = (close) => {
        this.data.found = false;
        this.data.finding = false;
        data.online.is_on = !close;
      }
      const menu = toTag('div')`
      <img src="data/gb.svg">
      </img>`({
          class: 'menu icon',
          '@click': () => {
            disconnect(true);
          }
      });
      const reset = toTag('div')``();
      const gen_range = () => {
        const max_gen = this.data.max_gen;
        if (max_gen == 1) return 'gen 1';
        return `gens 1-${max_gen}`;
      }
      const action_class = () => {
        return 'action' + (
          [' button',''][+this.data.finding]
        );
      }
      const ing = () => {
        return ['', 'ing'][+this.data.finding];
      }
      const action_text = () => {
        if (this.data.found) {
          return 'Disconnect?';
        }
        return `Search${ing()} gyms`
      }
      const action = toTag('div')`
        ${action_text}
      `({
        class: action_class,
        '@click': () => {
          if (this.data.found) {
            return disconnect(false);
          }
          if (this.data.finding) return;
          this.data.finding = true;
          this.draw();
        }
      })
      const header = () => {
        if (this.data.found) {
          return toTag('div')`
            Found gym! ${action} 
          `({
            class: 'header'
          });
        }
        return toTag('div')`
          ${action} of ${gen_range}
        `({
          class: 'header'
        });
      }
      const main_row = toTag('div')`
        ${reset}${header}${menu}
      `({
        class: 'main-row'
      });
      const badge_style = () => {
        const offset = this.data.badge_y;
        const badge_png = 'data/badges.png';
        return `
          width: 50px;
          height: 50px;
          background-size: 50px;
          background-position: center -${offset}px;
          background-image: url("${badge_png}");
        `;
      }
      const badges = toTag('div')``({
        style: badge_style,
        class: 'badge icon button',
        '@click': () => {
          disconnect(false);
          data.offerNewBadge(+1);
        }
      });
      const badge_name = () => {
        if (this.data.finding) return '...';
        const { all_gym_badges } = badge_info;
        const { badge_offer } = data.online;
        const s = all_gym_badges.get(
          badge_offer
        );
        if (!s) return ''
        return (
          s[0].toUpperCase() + s.slice(1) + ' badge'
        );
      }
      const whose = () => {
        return ['Your', 'Their'][+this.data.finding];
      }
      const badge_label = toTag('div')`
        ${whose} badge: ${badge_name}
      `();
      const minor_row = toTag('div')`
        <div></div>${badge_label}${badges}
      `({
        class: 'minor-row'
      });
      return toTag('div')`${main_row}${minor_row}`({
        class: () => {
          if (data.online.is_on) {
            return 'shown menu wrapper';
          }
          return 'hidden menu wrapper';
        }
      });
    }

    async draw() {
      await new Promise((resolve) => {
        // Rotate the badge wheel
        this.data.badge_y = (
          this.data.badge_y + 10
        ) % (50 * to_max_gym_badge(
          this.data.max_gen
        ));
        window.setTimeout(() => {
          window.requestAnimationFrame(resolve);
        }, 1000/15);
      });
      if (!this.data.finding) return;
      await this.draw();
    }

    connected() {
      this.draw();
    }

    get styles() {
      return [globalCSS, onlineCSS];
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

  return toTag('online', OnlineMenu)``({
    badge_y: () => {
      const { badge_offer } = data.online;
      return Math.max(
        50 * (badge_offer-1), 0
      );
    },
    max_gen: () => data.online.max_gen,
    is_on: () => data.online.is_on,
    class: 'parent menu'
  });

}

export { toOnlineMenu };
