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
        is_on: false,
        state: '',
        badge_y: 0
      };
    }

    set is_on(val) {
      data.online.is_on = val;
    } 

    get is_on() {
      return data.online.is_on;
    }

    get found() {
      if (!this.is_on) return false;
      return this.data.state == 'found';
    }

    get finding() {
      if (!this.is_on) return false;
      return this.data.state == 'finding';
    }

    get root() {
      const disconnect = (close) => {
        this.data.state = '';
        this.is_on = !close;
      }
      const menu_class = () => {
        return 'menu icon' + ['', ' found'][+this.found];
      }
      const menu = toTag('div')`
      <img src="data/gb.svg">
      </img>`({
          class: menu_class,
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
          [' button',''][+this.finding]
        );
      }
      const ing = () => {
        return ['', 'ing'][+this.finding];
      }
      const action_text = () => {
        if (this.found) {
          return 'Disconnect?';
        }
        return `Search${ing()} gyms`
      }
      const action = toTag('div')`
        ${action_text}
      `({
        class: action_class,
        '@click': () => {
          if (this.found) {
            return disconnect(false);
          }
          if (this.finding) return;
          this.data.state = 'finding';
          this.draw();
        }
      })
      const header = () => {
        if (this.found) {
          return toTag('div')`
            <div>Found gym!</div> ${action} 
          `({
            class: 'found header'
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
          const { finding } = this;
          disconnect(false);
          const nearest_badge = 1 + Math.floor(
            (this.data.badge_y + 25) / 50
          );
          const diff = finding ? 0 : 1;
          data.offerNewBadge(nearest_badge+diff);
        }
      });
      const badge_name = () => {
        if (this.finding) return '...';
        const { all_gym_badges } = badge_info;
        const { badge_offer } = data.online;
        const s = all_gym_badges.get(
          badge_offer
        );
        if (!s) return ''
        return (
          s[0].toUpperCase() + s.slice(1)
        );
      }
      const whose = () => {
        return ({
          '': 'Your badge:',
          'finding': 'Their badge:',
          'found': 'At stake:'
        })[this.data.state];
      }
      const badge_label = toTag('div')`
        ${whose}<div>${badge_name}</div>
      `({
        class: 'label'
      });
      const minor_row = toTag('div')`
        <div></div>${badge_label}${badges}
      `({
        class: 'minor-row'
      });
      return toTag('div')`${main_row}${minor_row}`({
        class: () => {
          if (this.is_on) {
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
        }, 1000/10);
      });
      if (!this.finding) return;
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
