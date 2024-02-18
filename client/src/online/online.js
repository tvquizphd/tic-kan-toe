import onlineCSS from 'online-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { badge_info } from 'badges';
import { toTag, CustomTag } from 'tag';

const toOnlineMenu = (data, actions) => {

  class OnlineMenu extends CustomTag {

    static get setup() {
      return {
        online: JSON.stringify(data.online)
      };
    }

    get root() {
      const menu = toTag('div')`
      <img src="data/gb.svg">
      </img>`({
          class: 'menu icon',
          '@click': () => {
            data.online.is_on = false;
          }
      });
      const reset = toTag('div')``();
      const header = toTag('div')`
        Multiplayer live on Monday!
      `();
      const main_row = toTag('div')`
        ${reset}${header}${menu}
      `({
        class: 'main-row'
      });
      const badge_style = () => {
        const { 
          badge_offer
        } = data.online;
        const offset = Math.max(
          50 * (badge_offer-1), 0
        );
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
        class: 'badge icon',
        '@click': () => {
          data.offerNewBadge(+1);
        }
      });
      const badge_name = () => {
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
      const badge_label = toTag('div')`${badge_name}`();
      const minor_row = toTag('div')`
        ${badge_label}${badges}
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
    online: () => JSON.stringify(data.online),
    class: 'parent menu'
  });

}

export { toOnlineMenu };
