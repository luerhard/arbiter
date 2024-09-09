import "../css/custom.scss";
// stupid workaround to load htmx due to missing UMD file. (required if we want htmx extensions to work)
import "./htmx.js";
import "htmx-ext-ws";
// boostrap-icons
import "bootstrap-icons/font/bootstrap-icons.scss";

// Place any custom JS here

htmx.logger = function (elt, event, data) {
    if (console) {
        console.log(event, elt, data);
    }
}

htmx.logAll();
