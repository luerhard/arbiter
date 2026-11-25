import "../css/coloris.min.css";
import "../css/main.css";

import Alpine from "alpinejs";
import focus from "@alpinejs/focus";
import morph from "@alpinejs/morph";
import sort from "@alpinejs/sort";
window.Alpine = Alpine;
Alpine.plugin(focus);
Alpine.plugin(morph);
Alpine.plugin(sort);

import "@tailwindplus/elements";
import htmx from "htmx.org";
window.htmx = htmx;
import "htmx-ext-ws";
import "htmx-ext-alpine-morph";

import "./vendor/coloris.min.js";

window.Coloris({
  el: "[data-coloris]",
  theme: "default",
  themeMode: "light",
  alpha: false,
  format: "hex",
  formatToggle: false,
  clearButton: false,
  closeButton: true,
  swatchesOnly: false, // if we only want to allow a pre-set of colors, change this to true
  focusInput: true,
  selectInput: true,
  defaultColor: "#3b82f6",
  swatches: [
    "#ef4444", // red-500
    "#f97316", // orange-500
    "#f59e0b", // amber-500
    "#eab308", // yellow-500
    "#84cc16", // lime-500
    "#22c55e", // green-500
    "#10b981", // emerald-500
    "#14b8a6", // teal-500
    "#06b6d4", // cyan-500
    "#0ea5e9", // sky-500
    "#3b82f6", // blue-500
    "#6366f1", // indigo-500
    "#8b5cf6", // violet-500
    "#a855f7", // purple-500
    "#d946ef", // fuchsia-500
    "#ec4899", // pink-500
    "#f43f5e", // rose-500
  ],
});
// Coloris adds its swatch (the colored square in the field) only to fields present at the call above; fields that htmx
// adds later, like a new label row on the project form, get it here.
htmx.onLoad((el) => window.Coloris.wrap(Array.from(el.querySelectorAll("[data-coloris]"))));

import { navBlock, labelButton, skipAnnotatedToggle } from "./annotation.js";
import { spanEditor } from "./spans.js";
import * as ui from "./ui.js";
import * as discuss from "./discuss.js";
import { initToasts } from "./toasts.js";
import { panelsStore, watchWidth } from "./panels.js";

window.lib = window.lib || {};
window.lib.ui = ui;
window.lib.discuss = discuss;

Alpine.data("labelButton", labelButton);
Alpine.data("navBlock", navBlock);
Alpine.data("skipAnnotatedToggle", skipAnnotatedToggle);
Alpine.data("spanEditor", spanEditor);
Alpine.store("panels", panelsStore());
watchWidth(Alpine.store("panels"));
Alpine.start();

// Debugging
htmx.logger = (elt, event, data) => console?.log?.(event, elt, data);
htmx.logAll();
initToasts(htmx);
