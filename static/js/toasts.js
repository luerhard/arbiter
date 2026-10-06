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
