import "../css/main.css";
import '@tailwindplus/elements';


import htmx from "htmx.org";
window.htmx = htmx;
import "htmx-ext-ws";

import Mousetrap from "mousetrap";

import Alpine from 'alpinejs';
window.Alpine = Alpine;

import { navBlock, labelButton } from "./annotation.js";
Alpine.data("labelButton", labelButton);
Alpine.data("navBlock", navBlock);

import { notification } from "./expert.js";
Alpine.data("notification", notification);

Alpine.start();

// Your modules
import * as funcs from "./functions.js";
import * as discuss from "./discuss.js";
import * as expert from "./expert.js";

window.lib = { funcs, discuss, expert };
export { funcs, discuss, expert };

// Debugging
// htmx.logger = (elt, event, data) => console?.log?.(event, elt, data);
// htmx.logAll();
