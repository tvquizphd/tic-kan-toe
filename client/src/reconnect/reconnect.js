import reconnectCSS from 'reconnect-css' assert { type: 'css' };
import globalCSS from 'global-css' assert { type: 'css' };
import { toTag, CustomTag } from 'tag';

const toReconnectModal = (data, actions) => {

  class ReconnectModal extends CustomTag {

    static get setup() {
      return {
        trying: 'try'
      };
    }

    get root() {

      const label = 'Please try to reconnect';
      const trying = () => {
        return this.data.trying;
      }
      const button = toTag('div')`${trying}`({
        'class': 'button',
        '@click': () => {
          if (this.data.trying == 'trying') {
            return;
          }
          data.ws_ping(false, 'hosting');
          this.data.trying = 'trying';
          setTimeout(() => {
            this.data.trying = 'retry';
          }, 3000);
        }
      });

      const center = toTag('div')`<h3>${label}</h3>${button}`({
        class: 'center',
        '@click': (e) => {
          e.stopPropagation();
        }
      });

      return toTag('div')`
        ${center}`({
        class: () => {
          if (data.modal == 'reconnect') {
            return 'shown modal wrapper';
          }
          return 'hidden modal wrapper';
        }
      });
    }

    get styles() {
      const sheet = new CSSStyleSheet();
      sheet.replaceSync(`
      .todo {
      }`);
      return [globalCSS, reconnectCSS, sheet];
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

  return toTag('reconnect', ReconnectModal)``({
    class: 'parent modal'
  });

}

export { toReconnectModal };
