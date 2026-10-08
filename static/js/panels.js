// Open state of the side panels on the work screens (cotton/side_panel), as the Alpine store "panels".
// From xl up a panel sits beside the content and is open unless closed; that choice is remembered per panel
// (localStorage "<name>Panel"). Below xl panels slide over the content: closed until opened, one at a time.
const wideQuery = window.matchMedia("(min-width: 80rem)");

function remembered(name) {
  try {
    return localStorage.getItem(`${name}Panel`) !== "closed";
  } catch (e) {
    return true;
  }
}

export function panelsStore() {
  return {
    wide: wideQuery.matches,
    wideOpen: {}, // name -> open, once toggled from xl up
    overlay: null, // name of the panel open below xl

    isOpen(name) {
      if (!this.wide) return this.overlay === name;
      return name in this.wideOpen ? this.wideOpen[name] : remembered(name);
    },
    toggle(name) {
      if (!this.wide) {
        this.overlay = this.overlay === name ? null : name;
        return;
      }
      this.wideOpen[name] = !this.isOpen(name);
      try {
        localStorage.setItem(`${name}Panel`, this.wideOpen[name] ? "open" : "closed");
      } catch (e) {}
    },
    closeOverlay() {
      this.overlay = null;
    },
  };
}

export function watchWidth(store) {
  wideQuery.addEventListener("change", (event) => {
    store.wide = event.matches;
    store.overlay = null;
  });
}
