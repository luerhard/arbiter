import "../css/main.css";
import '@tailwindplus/elements';

import htmx from "htmx.org";
window.htmx = htmx;
await import("htmx-ext-ws");
import Mousetrap from "mousetrap";
import Alpine from 'alpinejs'
window.Alpine = Alpine

import { navBlock, labelButton } from "./annotation.js";
Alpine.data("labelButton", labelButton);
Alpine.data("navBlock", navBlock);

Alpine.start()

// Your modules
import * as funcs from "./functions.js";
import * as discuss from "./discuss.js";

window.lib = { funcs, discuss };
export { funcs, discuss };

// Debugging
htmx.logger = (elt, event, data) => console?.log?.(event, elt, data);
htmx.logAll();
