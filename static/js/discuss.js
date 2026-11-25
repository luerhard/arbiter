export function renderOnlineStatus(online_users) {
  const exampleField = document.getElementById("n-online-status");
  const count = Array.isArray(online_users) ? online_users.length : 0;
  exampleField.innerText = count;
}

// Width of the discussion chat (discuss/index.html): from md up the user drags the bar at its left edge, or focuses it
// and uses the arrow keys; a double click goes back to the default width. The chosen width is remembered
// (localStorage "chatWidth") and set as --chat-w. The CSS there caps it: wider than the default only while the main
// column keeps half the window, codebook open or not. --chat-width is the width the chat really has, for the codebook
// panel that slides in beside it.
const CHAT_MIN_WIDTH = 280;
const CHAT_KEY_STEP = 20;

export function chatResizer() {
  let stored = null;
  try {
    stored = parseInt(localStorage.getItem("chatWidth"), 10) || null;
  } catch (e) {}

  return {
    width: stored, // null: the default width from the CSS
    actual: 0,

    init() {
      const chat = this.$refs.chat;
      new ResizeObserver(() => (this.actual = chat.offsetWidth)).observe(chat);
    },
    get vars() {
      return { "--chat-w": this.width ? `${this.width}px` : null, "--chat-width": `${this.actual}px` };
    },
    // the CSS has the last word on the width; keep the chosen one at what is shown, so that dragging back from past
    // the cap moves the bar at once
    resize(px) {
      this.width = Math.round(Math.max(px, CHAT_MIN_WIDTH));
      return this.$nextTick(() => (this.width = Math.min(this.width, this.$refs.chat.offsetWidth)));
    },
    remember() {
      try {
        if (this.width) localStorage.setItem("chatWidth", this.width);
        else localStorage.removeItem("chatWidth");
      } catch (e) {}
    },
    startDrag(event) {
      event.preventDefault(); // no text selection while dragging
      const handle = event.currentTarget;
      const right = this.$refs.chat.getBoundingClientRect().right;
      handle.setPointerCapture(event.pointerId);
      let last = Promise.resolve();
      const move = (e) => (last = this.resize(right - e.clientX));
      const stop = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", stop);
        handle.removeEventListener("pointercancel", stop);
        last.then(() => this.remember());
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    },
    // the bar is left of the chat: left makes the chat wider
    step(direction) {
      this.resize(this.$refs.chat.offsetWidth + direction * CHAT_KEY_STEP).then(() => this.remember());
    },
    reset() {
      this.width = null;
      this.remember();
    },
  };
}
