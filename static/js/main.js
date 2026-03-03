import "../css/coloris.min.css";
import "../css/main.css";

import "@tailwindplus/elements";
import htmx from "htmx.org";
window.htmx = htmx;
import "htmx-ext-ws";

import Mousetrap from "mousetrap";
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
    "#64748b", // slate-500
    "#6b7280", // gray-500
    "#71717a", // zinc-500
    "#737373", // neutral-500
    "#78716c", // stone-500
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

import Alpine from "alpinejs";
import focus from "@alpinejs/focus";
window.Alpine = Alpine;
Alpine.plugin(focus);

import { navBlock, labelButton } from "./annotation.js";
import * as ui from "./ui.js";
import * as funcs from "./functions.js";
import * as discuss from "./discuss.js";
import { initToasts } from "./toasts.js";

window.lib = window.lib || {};
window.lib.ui = ui;
window.lib.funcs = funcs;
window.lib.discuss = discuss;

Alpine.data("labelButton", labelButton);
Alpine.data("navBlock", navBlock);
Alpine.start();

// Debugging
htmx.logger = (elt, event, data) => console?.log?.(event, elt, data);
htmx.logAll();
initToasts(htmx);
