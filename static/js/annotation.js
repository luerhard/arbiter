export function navBlock({ hasPrev, hasNext, saveFormId }) {
    return {
        hasPrev: !!hasPrev,
        hasNext: !!hasNext,
        saveFormId: saveFormId || 'label-form',
        busy: false,

        init() {
            // global keybinds (ignore when typing)
            this._onKey = (e) => {
                const t = e.target;
                const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
                if (typing) return;

                if (e.key === 'ArrowLeft' && this.hasPrev && !this.busy) {
                    e.preventDefault();
                    this.$refs.prev?.click();
                } else if (e.key === 'ArrowRight' && this.hasNext && !this.busy) {
                    e.preventDefault();
                    this.$refs.next?.click();
                } else if (e.key === 'Enter' && !this.busy) {
                    e.preventDefault();
                    const form = document.getElementById(this.saveFormId);
                    form?.requestSubmit ? form.requestSubmit() : form?.submit();
                }
            };
            window.addEventListener('keydown', this._onKey);

            // HTMX request lifecycle → toggle busy
            this._onBefore = () => { this.busy = true; };
            this._onAfter = () => { this.busy = false; };
            window.addEventListener('htmx:beforeRequest', this._onBefore);
            window.addEventListener('htmx:afterOnLoad', this._onAfter);

            // Clean-up when Alpine component is destroyed (e.g., HTMX swap)
            this.$el.addEventListener('alpine:destroy', () => {
                window.removeEventListener('keydown', this._onKey);
                window.removeEventListener('htmx:beforeRequest', this._onBefore);
                window.removeEventListener('htmx:afterOnLoad', this._onAfter);
            }, { once: true });
        }
    };
}
export function labelButton({ id, hotkey, disabled}) {
    return {
        id,
        hotkey,
        disabled: !!disabled,
        _onKey: null,

        init() {
            if (this.hotkey && !this.disabled) {
                this._onKey = (e) => {
                    const t = e.target;
                    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
                    if (e.key.toLowerCase() === String(this.hotkey).toLowerCase()) {
                        e.preventDefault();
                        this.$refs.input?.click();
                    }
                };
                window.addEventListener('keydown', this._onKey);

                // Proper cleanup in Alpine:
                this.$el.addEventListener('alpine:destroy', () => {
                    if (this._onKey) window.removeEventListener('keydown', this._onKey);
                }, { once: true });
            }
        }
    };
}
