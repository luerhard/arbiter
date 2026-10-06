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
  svg.setAttribute("stroke-width", "1.8");
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
    path.setAttribute("d", "M12 16v-4.5m0-3h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z");
  }

  svg.appendChild(path);
  return svg;
}

function applyToastVariant(element, tags) {
  if (!element) return;

  // colors come from .toast[data-variant=...] in main.css
  const variant = resolveToastVariant(tags);
  element.dataset.variant = variant;

  const iconHost = element.querySelector("[data-toast-icon]");
  if (iconHost) {
    const icon = { success: "check-circle", error: "x-circle" }[variant] ?? "info-circle";
    iconHost.replaceChildren(iconSvg(icon, "toast-icon"));
  }
}

function showToastElement(element, { delay = 2000 } = {}) {
  if (!element) return;

  const closeButton = element.querySelector("[data-toast-close]");
  if (closeButton) {
    closeButton.addEventListener("click", () => removeToast(element), { once: true });
  }

  element.classList.add("transition", "duration-200", "ease-out", "transform", "opacity-0", "-translate-y-1");

  requestAnimationFrame(() => {
    element.classList.remove("opacity-0", "-translate-y-1");
  });

  window.setTimeout(() => removeToast(element), delay);
}

function createToast(htmx, message) {
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

export function initToasts(htmx) {
  document.querySelectorAll("[data-toast]").forEach((element) => {
    applyToastVariant(element, element.dataset.toastTags);
    showToastElement(element);
  });

  htmx.on("messages", (e) => {
    (e?.detail?.value ?? []).forEach((message) => createToast(htmx, message));
  });
}
