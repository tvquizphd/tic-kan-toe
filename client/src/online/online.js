import onlineCSS from 'online-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { toTag, CustomTag } from 'tag';

const toOnlineMenu = (data, actions) => {

  class OnlineMenu extends CustomTag {

    static get setup() {
      return {
        online: data.online
      };
    }

    get root() {
      const menu = toTag('div')`
      <img src="data/gb.svg">
      </img>`({
          class: 'menu icon',
          '@click': () => {
            data.resetRevive();
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
      return toTag('div')`${main_row}`({
        class: () => {
          if (this.data.online.is_on) {
            return 'shown menu wrapper';
          }
          return 'hidden menu wrapper';
        },
        '@click': () => {
          data.online.is_on = false;
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
    is_on: () => JSON.stringify(data.online),
    class: 'parent menu'
  });

}

export { toOnlineMenu };
