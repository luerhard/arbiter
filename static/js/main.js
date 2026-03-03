import "../css/main.css";
import "@tailwindplus/elements";

import htmx from "htmx.org";
window.htmx = htmx;
import "htmx-ext-ws";

import Mousetrap from "mousetrap";

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
