// Span annotation: the text as words, labeled passages as highlights. The server splits
// the text into words (with their offsets into it); a span is [labelId, start, end] and
// always covers whole words.
//
// Select words (or click one), then choose a label. Choosing a label first (click or key)
// labels every following selection right away; Escape stops it. While dragging, the
// selection already shows as the words it will cover; a selection that starts or ends
// outside the text covers it up to its first or last word. In read-only mode `others` are
// the spans of the other annotators: what everyone has is shown faded, so the differences
// stand out.

const isTyping = (el) => el?.isContentEditable || ["INPUT", "TEXTAREA"].includes(el?.tagName);

export function spanEditor({ tokens, labels, spans = [], readonly = false, locked = false, others = [] }) {
  const firstWord = new Map(tokens.map((t, i) => [t.start, i]));
  const lastWord = new Map(tokens.map((t, i) => [t.end, i]));

  return {
    tokens,
    labels,
    spans,
    readonly,
    locked, // saved in the discussion, see the lock-labels event
    active: null, // label id that every selection gets
    pending: null, // [from, to] word indices of a selection waiting for a label
    selecting: null, // [from, to] of the selection while dragging
    hovered: null, // span highlighted from the list

    init() {
      this._listening = new AbortController();
      const signal = this._listening.signal;
      window.addEventListener("keydown", (e) => this.onKey(e), { signal });
      document.addEventListener("selectionchange", () => (this.selecting = this.selected()), { signal });
      // released anywhere, also outside the text
      window.addEventListener("mouseup", () => this.select(), { signal });
    },

    destroy() {
      this._listening.abort();
    },

    onKey(e) {
      if (!this.editable || isTyping(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "Escape") {
        this.pending = this.active = null;
        return;
      }
      const label = this.labels.find((l) => l.hotkey && l.hotkey.toLowerCase() === e.key.toLowerCase());
      if (label) {
        e.preventDefault();
        this.choose(label.id);
      }
    },

    get editable() {
      return !this.readonly && !this.locked;
    },

    get value() {
      return JSON.stringify(this.spans);
    },

    get sorted() {
      return [...this.spans].sort((a, b) => a[1] - b[1] || a[2] - b[2] || a[0] - b[0]);
    },

    get hint() {
      if (this.pending) return "Choose a label for the selected words. Esc cancels.";
      if (this.active)
        return `Every selection becomes “${this.label(this.active).name}”. Esc or the label again stops.`;
      return "Select words in the text, then choose a label. Or choose a label first to mark several passages.";
    },

    label(id) {
      return this.labels.find((l) => l.id === id);
    },

    words(span) {
      return [firstWord.get(span[1]), lastWord.get(span[2])];
    },

    quote(span) {
      const [from, to] = this.words(span);
      return this.tokens
        .slice(from, to + 1)
        .map((t, i) => t.text + (from + i < to ? t.gap : ""))
        .join("");
    },

    // the spans covering word i; with gap, those covering the whitespace after it
    covering(i, gap = false) {
      const t = this.tokens[i];
      const next = gap ? this.tokens[i + 1] : t;
      if (!next) return [];
      return this.spans.filter(([, start, end]) => start <= t.start && next.end <= end);
    },

    shared(span) {
      const key = span.join();
      return others.length > 0 && others.every((theirs) => theirs.some((s) => s.join() === key));
    },

    style(i, gap = false) {
      const covering = this.covering(i, gap);
      const marked = this.selecting ?? this.pending;
      if (marked && marked[0] <= i && i + (gap ? 1 : 0) <= marked[1]) {
        const color = this.active ? this.label(this.active).color : "var(--c-accent)";
        return {
          background: `color-mix(in srgb, ${color} 16%, transparent)`,
          boxShadow: `inset 0 -2px 0 ${color}`,
        };
      }
      if (!covering.length) return {};
      const hovered = this.hovered && covering.includes(this.hovered);
      const stripes = covering.map((span, n) => {
        const color = this.label(span[0]).color;
        const strength = this.shared(span) ? 35 : 100;
        return `inset 0 ${-3 * (n + 1)}px 0 color-mix(in srgb, ${color} ${strength}%, transparent)`;
      });
      const tint = hovered ? 35 : covering.every((s) => this.shared(s)) ? 6 : 16;
      return {
        background: `color-mix(in srgb, ${this.label(covering[0][0]).color} ${tint}%, transparent)`,
        boxShadow: stripes.join(", "),
      };
    },

    // the word a selection starts or ends at; in the whitespace after word i, that is
    // word i + 1 for the start and word i for the end
    wordAt(node, offset, side) {
      const el = (node.nodeType === Node.TEXT_NODE ? node.parentElement : node)?.closest("[data-i], [data-gap]");
      if (!el || !this.$refs.text.contains(el)) return null;
      if (el.dataset.gap !== undefined) return Number(el.dataset.gap) + (side === "start" ? 1 : 0);
      const i = Number(el.dataset.i);
      // a double click selects up to the very start of the next word
      return side === "end" && offset === 0 && node.nodeType === Node.TEXT_NODE ? i - 1 : i;
    },

    // the words of the current selection, [from, to]; outside the text, its start and end
    // snap to the first and last word it covers
    selected() {
      const selection = window.getSelection();
      if (!this.editable || !selection.rangeCount) return null;
      const range = selection.getRangeAt(0);
      const words = [...this.$refs.text.querySelectorAll("[data-i]")].filter((el) => range.intersectsNode(el));
      if (!words.length) return null;
      const from = this.wordAt(range.startContainer, range.startOffset, "start") ?? Number(words[0].dataset.i);
      const to = this.wordAt(range.endContainer, range.endOffset, "end") ?? Number(words.at(-1).dataset.i);
      return from <= to ? [from, to] : null;
    },

    select() {
      // read again: after a click, selectionchange only comes after the mouseup
      const words = this.selected();
      this.selecting = null;
      if (!words) return;
      const [from, to] = words;
      window.getSelection().removeAllRanges();
      if (this.active) this.add(this.active, from, to);
      else this.pending = [from, to];
    },

    choose(labelId) {
      if (this.pending) {
        this.add(labelId, ...this.pending);
        this.pending = null;
      } else {
        this.active = this.active === labelId ? null : labelId;
      }
    },

    // the same passage with the same label again removes it; spans of one label that
    // overlap or follow each other word by word become one (as on the server)
    add(labelId, from, to) {
      const span = [labelId, this.tokens[from].start, this.tokens[to].end];
      if (this.spans.some((s) => s.join() === span.join())) return this.remove(span);
      const merged = [];
      for (const s of [...this.spans, span].sort((a, b) => a[0] - b[0] || a[1] - b[1])) {
        const last = merged.at(-1);
        if (last && last[0] === s[0] && this.words(s)[0] <= this.words(last)[1] + 1) {
          last[2] = Math.max(last[2], s[2]);
        } else {
          merged.push([...s]);
        }
      }
      this.spans = merged;
    },

    remove(span) {
      const key = span.join();
      this.spans = this.spans.filter((s) => s.join() !== key);
      this.hovered = null;
    },
  };
}
