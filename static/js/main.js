import "../css/main.css";
import '@tailwindplus/elements';


import htmx from "htmx.org";
window.htmx = htmx;
import "htmx-ext-ws";

import Mousetrap from "mousetrap";

import Alpine from 'alpinejs';
import focus from "@alpinejs/focus";
window.Alpine = Alpine;
Alpine.plugin(focus);

import * as ui from "./ui.js";
import * as funcs from "./functions.js";
import * as discuss from "./discuss.js";

window.lib = window.lib || {};
window.lib.ui = ui;
window.lib.funcs = funcs;
window.lib.discuss = discuss;

Alpine.start();

// Debugging
htmx.logger = (elt, event, data) => console?.log?.(event, elt, data);
htmx.logAll();

function removeToast(element) {
    if (!element) return;
    element.classList.add("opacity-0", "-translate-y-1");
    window.setTimeout(() => element.remove(), 200);
}

function resolveToastVariant(tags) {
    const normalized = (tags ?? "").toLowerCase();
    if (normalized.includes("error") || normalized.includes("danger")) return "error";
    if (normalized.includes("warning")) return "warning";
    if (normalized.includes("success")) return "success";
    if (normalized.includes("info") || normalized.includes("primary")) return "info";
    return "info";
}

function iconSvg(icon, className) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.5");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", className);

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");

    if (icon === "check-circle") {
        path.setAttribute("d", "M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z");
    } else if (icon === "x-circle") {
        path.setAttribute("d", "m9.75 9.75 4.5 4.5m0-4.5-4.5 4.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z");
    } else {
        path.setAttribute("d", "m15 11.25-3-3m0 0-3 3m3-3v7.5M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z");
    }

    svg.appendChild(path);
    return svg;
}

function applyToastVariant(element, tags) {
    if (!element) return;

    const variant = resolveToastVariant(tags);
    element.classList.remove(
        "bg-white",
        "dark:bg-gray-800",
        "outline-black/5",
        "dark:outline-white/10",
    );

    const body = element.querySelector("[data-toast-body]");
    if (body) {
        body.classList.remove("text-gray-900", "dark:text-white");
    }

    const iconHost = element.querySelector("[data-toast-icon]");
    if (iconHost) {
        iconHost.replaceChildren();
    }

    if (variant === "success") {
        element.classList.add(
            "bg-green-50",
            "text-green-900",
            "outline-green-900/10",
            "dark:bg-green-900/30",
            "dark:text-green-100",
            "dark:outline-green-500/20",
        );
        if (body) body.classList.add("text-green-900", "dark:text-green-100");
        iconHost?.appendChild(iconSvg("check-circle", "size-6 text-green-400"));
    } else if (variant === "error") {
        element.classList.add(
            "bg-red-50",
            "text-red-900",
            "outline-red-900/10",
            "dark:bg-red-900/30",
            "dark:text-red-100",
            "dark:outline-red-500/20",
        );
        if (body) body.classList.add("text-red-900", "dark:text-red-100");
        iconHost?.appendChild(iconSvg("x-circle", "size-6 text-red-400"));
    } else if (variant === "warning") {
        element.classList.add(
            "bg-amber-50",
            "text-amber-900",
            "outline-amber-900/10",
            "dark:bg-amber-900/25",
            "dark:text-amber-100",
            "dark:outline-amber-500/20",
        );
        if (body) body.classList.add("text-amber-900", "dark:text-amber-100");
        iconHost?.appendChild(iconSvg("arrow-up-circle", "size-6 text-amber-400"));
    } else {
        element.classList.add(
            "bg-indigo-50",
            "text-indigo-900",
            "outline-indigo-900/10",
            "dark:bg-indigo-900/30",
            "dark:text-indigo-100",
            "dark:outline-indigo-500/20",
        );
        if (body) body.classList.add("text-indigo-900", "dark:text-indigo-100");
        iconHost?.appendChild(iconSvg("arrow-up-circle", "size-6 text-indigo-400"));
    }
}

function showToastElement(element, { delay = 2000 } = {}) {
    if (!element) return;

    const closeButton = element.querySelector("[data-toast-close]");
    if (closeButton) {
        closeButton.addEventListener("click", () => removeToast(element), { once: true });
    }

    element.classList.add(
        "transition",
        "duration-200",
        "ease-out",
        "transform",
        "opacity-0",
        "-translate-y-1",
    );

    requestAnimationFrame(() => {
        element.classList.remove("opacity-0", "-translate-y-1");
    });

    window.setTimeout(() => removeToast(element), delay);
}

function createToast(message) {
    const template = htmx.find("[data-toast-template]");
    if (!template) return;

    const element = template.cloneNode(true);
    delete element.dataset.toastTemplate;
    element.classList.remove("hidden");

    const body = element.querySelector("[data-toast-body]");
    if (body) body.innerText = message.message ?? "";

    applyToastVariant(element, message.tags);

    const stack = document.querySelector("[data-toast-stack]") ?? document.querySelector("[data-toast-container]");
    stack?.appendChild(element);

    showToastElement(element);
}

document.querySelectorAll("[data-toast]").forEach((element) => {
    applyToastVariant(element, element.dataset.toastTags);
    showToastElement(element);
});

htmx.on("messages", (e) => {
    (e?.detail?.value ?? []).forEach(createToast);
});
