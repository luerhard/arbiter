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

function applyToastVariant(element, tags) {
  // colors and the matching icon come from .toast[data-variant=...] in main.css
  if (element) element.dataset.variant = resolveToastVariant(tags);
}

// errors stay longer: they usually mean the user has to do something
function toastDelay(element) {
  return element?.dataset.variant === "error" ? 8000 : 2000;
}

function showToastElement(element, { delay = toastDelay(element) } = {}) {
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

function showErrorOnce(htmx, message) {
  const shown = [...document.querySelectorAll("[data-toast-body]")].some((body) => body.innerText === message);
  if (!shown) createToast(htmx, { message, tags: "error" });
}

export function initToasts(htmx) {
  document.querySelectorAll("[data-toast]").forEach((element) => {
    applyToastVariant(element, element.dataset.toastTags);
    showToastElement(element);
  });

  htmx.on("messages", (e) => {
    (e?.detail?.value ?? []).forEach((message) => createToast(htmx, message));
  });

  // A request that never reaches the server, or fails on it, swaps nothing: without a
  // message the page just stays as it is, and the user believes the change was saved.
  // The notification polling stays quiet, it tries again on its own.
  const polling = (e) => e.detail.elt?.id === "notification-stack";
  htmx.on("htmx:sendError", (e) => {
    if (polling(e)) return;
    const saving = e.detail.requestConfig?.verb !== "get";
    showErrorOnce(
      htmx,
      saving
        ? "Not saved: the server could not be reached. Check your connection and try again."
        : "The server could not be reached. Check your connection and try again.",
    );
  });
  htmx.on("htmx:responseError", (e) => {
    // 4xx answers bring their own message (e.g. "This decision is already saved")
    if (polling(e) || e.detail.xhr.status < 500) return;
    showErrorOnce(htmx, "Something went wrong on the server. Please try again.");
  });
}
