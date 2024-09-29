import "../css/custom.scss";
// stupid workaround to load htmx due to missing UMD file. (required if we want htmx extensions to work)
import "./htmx.js";
import "htmx-ext-ws";
// boostrap-icons
import "bootstrap-icons/font/bootstrap-icons.scss";
import * as bootstrap from 'bootstrap';
// Place any custom JS here

import * as funcs from "./functions";
import * as discuss from "./discuss";

export { funcs, discuss };

// for debugging
htmx.logger = function (elt, event, data) {
    if (console) {
        console.log(event, elt, data);
    }
}

htmx.logAll();

function createToast(message) {
    // Clone the template
    const element = htmx.find("[data-toast-template]").cloneNode(true)

    // Remove the data-toast-template attribute
    delete element.dataset.toastTemplate

    // Set the CSS class
    element.className += " " + message.tags

    // Set the text
    htmx.find(element, "[data-toast-body]").innerText = message.message

    // Add the new element to the container
    htmx.find("[data-toast-container]").appendChild(element)

    // Show the toast using Bootstrap's API
    const toast = new bootstrap.Toast(element, { delay: 2000 })
    toast.show()
}


htmx.on("messages", (e) => {
    e.detail.value.forEach(createToast)
})
