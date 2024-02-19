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
        ws_state: data.ws_state,
        is_on: false,
        badge_y: 0
      };
    }

    set is_on(val) {
      data.ws_ping(val, data.ws_state)
    } 

    get is_on() {
      return data.online.is_on;
    }

    get found() {
      if (!this.is_on) return false;
      return data.ws_state == 'found';
    }

    get finding() {
      if (!this.is_on) return false;
      return data.ws_state == 'finding';
    }

    get root() {
      const broadcast = (ws_state) => {
        data.ws_ping(this.is_on, ws_state);
      }
      const disconnect = (ws_state) => {
        data.ws_ping(false, ws_state);
      }
      const menu_class = () => {
        return 'menu icon' + ['', ' found'][+this.found];
      }
      const menu = toTag('div')`
      <img src="data/gb.svg">
      </img>`({
          class: menu_class,
          '@click': () => {
            disconnect('hosting');
          }
      });
      const reset = toTag('div')``();
      const gen_range = () => {
        const max_gen = this.data.max_gen;
        if (max_gen == 1) return 'gen 1';
        return `gens 1-${max_gen}`;
      }
      const ing = () => {
        return ['', 'ing'][+this.finding];
      }
      const action_text = () => {
        if (this.found) {
          return 'Disconnect?';
        }
        return `Search${ing()} all gyms`
      }
      const action_class = () => {
        return 'cancel action' + (
          [' button',''][+this.finding]
        );
      }
      const action = toTag('div')`
        ${action_text}
      `({
        class: action_class,
        '@click': () => {
          if (this.found) {
            broadcast('leaving');
            return;
          }
          if (this.finding) return;
          data.ws_ping(this.is_on, 'finding');
          this.draw();
        }
      })
      const header = () => {
        if (this.found) {
          const gen = this.data.max_gen;
          const [gen_plural, gen_str] = [
            ['', ''], ['s', ` - ${gen}`]
          ][+(gen > 1)];
          return toTag('div')`
            <div>Start Battling!</div> 
            (gen${gen_plural} 1${gen_str})
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
      const to_menu = () => {
        if (!this.found) return menu;
        return '';
      }
      const main_row = toTag('div')`
        ${reset}${header}${to_menu}
      `({
        class: 'main-row'
      });
      const badge_style = () => {
        const offset = this.data.badge_y;
        const round_offset = !this.finding ? (
          Math.round(offset / 50) * 50
        ) : offset
        const badge_png = 'data/badges.png';
        return `
          width: 50px;
          height: 50px;
          background-size: 50px;
          background-position: center -${round_offset}px;
          background-image: url("${badge_png}");
        `;
      }
      const badges = toTag('div')``({
        style: badge_style,
        class: 'badge icon button',
        '@click': () => {
          const { finding, found } = this;
          if (found) return;
          broadcast('hosting');
          const nearest_badge = 1 + Math.floor(
            (this.data.badge_y + 25) / 50
          );
          const diff = finding ? 0 : 1;
          data.offerNewBadge(nearest_badge+diff);
        }
      });
      const badge_status = () => {
        if (this.finding) {
          return toTag('div')`cancel`({
            class: 'cancel button',
            '@click': () => {
              disconnect('hosting');
            }
          });
        }
        const { all_gym_badges } = badge_info;
        const { badge_offer } = data.online;
        const s = all_gym_badges.get(
          badge_offer
        );
        const badge_name = () => {
          return s ? (
            s[0].toUpperCase() + s.slice(1)
          ): '';
        }
        return toTag('div')`${badge_name}`();
      }
      const whose = () => {
        return ({
          'hosting': 'Your badge:',
          'finding': 'Seeking badges:',
          'found': 'At stake:'
        })[data.ws_state];
      }
      const found_label = () => {
        if (this.found) {
          return toTag('div')`
            <div>Found a Gym!</div> ${action} 
          `({
            class: 'found label'
          });
        }
        return toTag('div')`
          <div>No battle</div><div>...yet</div>
        `({
          class: 'label'
        });
      }
      const badge_label = toTag('div')`
        ${whose}${badge_status}
      `({
        class: 'label'
      });
      const minor_row = toTag('div')`
        ${found_label}<div></div>${badge_label}${badges}
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
    ws_state: () => data.ws_state,
    max_gen: () => data.online.max_gen,
    is_on: () => data.online.is_on,
    class: 'parent menu'
  });

}

export { toOnlineMenu };
