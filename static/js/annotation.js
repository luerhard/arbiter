// Keys typed into a text field are text, not shortcuts. A checkbox is an INPUT too, but it
// is not typing: clicking a label focuses its hidden checkbox, and the shortcuts must keep
// working after that.
function isTyping(target) {
  if (!target) return false;
  if (target.isContentEditable || target.tagName === "TEXTAREA") return true;
  return target.tagName === "INPUT" && !["checkbox", "radio"].includes(target.type);
}

// Ctrl/Cmd/Alt combinations belong to the browser (Ctrl+P prints, Alt+← goes back).
function hasModifier(e) {
  return e.ctrlKey || e.metaKey || e.altKey;
}

export function navBlock({ hasPrev, hasNext, saveFormId }) {
  return {
    hasPrev: !!hasPrev,
    hasNext: !!hasNext,
    saveFormId: saveFormId || "label-form",
    busy: false,

    init() {
      // global keybinds (ignore when typing)
      this._onKey = (e) => {
        if (isTyping(e.target) || hasModifier(e)) return;

        if (e.key === "ArrowLeft" && this.hasPrev && !this.busy) {
          e.preventDefault();
          this.$refs.prev?.click();
        } else if (e.key === "ArrowRight" && this.hasNext && !this.busy) {
          e.preventDefault();
          this.$refs.next?.click();
        } else if (e.key === "Enter" && !this.busy) {
          e.preventDefault();
          const form = document.getElementById(this.saveFormId);
          form?.requestSubmit ? form.requestSubmit() : form?.submit();
        }
      };

      window.addEventListener("keydown", this._onKey);

      // Clean up when this Alpine component is removed (e.g. htmx swaps panel).
      this.$el.addEventListener(
        "alpine:destroy",
        () => {
          if (this._onKey) window.removeEventListener("keydown", this._onKey);
        },
        { once: true },
      );
    },
  };
}

export function skipAnnotatedToggle() {
  return {
    on: new URLSearchParams(window.location.search).get("skip_annotated") === "1",
    toggle() {
      const url = new URL(window.location.href);
      if (this.on) {
        url.searchParams.delete("skip_annotated");
      } else {
        url.searchParams.set("skip_annotated", "1");
      }
      window.location.href = url.toString();
    },
  };
}

export function labelButton({ id, hotkey, disabled }) {
  const isDisabled = (value) => {
    if (typeof value === "boolean") return value;
    if (value == null) return false;
    const normalized = String(value).trim().toLowerCase();
    return normalized === "true" || normalized === "disabled" || normalized === "1";
  };

  return {
    id,
    hotkey,
    disabled: isDisabled(disabled),
    _onKey: null,

    init() {
      if (this.hotkey && !this.disabled) {
        this._onKey = (e) => {
          if (isTyping(e.target) || hasModifier(e)) return;
          if (e.key.toLowerCase() === String(this.hotkey).toLowerCase()) {
            e.preventDefault();
            this.$refs.input?.click();
          }
        };
        window.addEventListener("keydown", this._onKey);

        // Proper cleanup in Alpine:
        this.$el.addEventListener(
          "alpine:destroy",
          () => {
            if (this._onKey) window.removeEventListener("keydown", this._onKey);
          },
          { once: true },
        );
      }
    },
  };
}
