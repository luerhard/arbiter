export function renderPrevLabels(labels, user) {
    const container = document.getElementById("prev-labels");
    container.innerHTML = "";

    let myBlock = null; // defer "me" to append last

    // helper: flatten [[{...}], [{...}]] -> [{...}, {...}]
    const flatten = (arr) => (Array.isArray(arr) ? arr.flat(1).filter(Boolean) : []);

    for (const [username, rawList] of Object.entries(labels || {})) {
        const labelList = flatten(rawList);

        const block = document.createElement("div");
        block.className = "my-3";

        const title = document.createElement("p");
        title.className = "d-flex mt-3 mb-3";
        title.textContent =
            username === user ? "Your previous annotations:" : `Previous annotations of ${username}:`;
        block.appendChild(title);

        const grid = document.createElement("div");
        grid.className = "label-grid";

        for (const lbl of labelList) {
            const id = `${username}-${String(lbl.id)}`;

            const checkbox = document.createElement("input");
            checkbox.disabled = true;
            checkbox.id = id;
            checkbox.type = "checkbox";
            checkbox.className = "btn-check btn-check-color";
            checkbox.checked = !!lbl.is_set;
            grid.appendChild(checkbox);

            const checkboxLabel = document.createElement("label");
            checkboxLabel.textContent = lbl.label;
            checkboxLabel.htmlFor = id;
            checkboxLabel.className = "btn btn-custom-color";
            checkboxLabel.style.setProperty("--label-color", String(lbl.color ?? "").trim());
            grid.appendChild(checkboxLabel);
        }

        block.appendChild(grid);

        if (username === user) {
            myBlock = block; // append mine last
        } else {
            container.appendChild(block);
        }
    }

    if (myBlock) container.appendChild(myBlock);
}


export function renderCurrentLabels(labels, user) {
    const container = document.getElementById("current-labels");
    container.innerHTML = "";

    const title = document.createElement("p");
    title.className = "mt-3 mb-3";
    title.textContent = "Your revised annotation:";
    container.appendChild(title);

    const grid = document.createElement("div");
    grid.className = "label-grid";
    container.appendChild(grid);

    // flatten [[{...}], [{...}]] -> [{...}, {...}]
    const flatten = (arr) => (Array.isArray(arr) ? arr.flat(1).filter(Boolean) : []);
    const myLabels = flatten((labels || {})[user] || []);

    for (const lbl of myLabels) {
        const id = String(lbl.id);

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "btn-check btn-check-color";
        checkbox.id = id;                 // keep numeric id to match collectLabels()
        checkbox.name = `label_${id}`;
        checkbox.value = id;
        checkbox.checked = !!lbl.is_set;  // preselect from previous labels
        grid.appendChild(checkbox);

        const labelEl = document.createElement("label");
        labelEl.className = "btn btn-custom-color";
        labelEl.htmlFor = id;
        labelEl.textContent = lbl.label;
        labelEl.style.setProperty("--label-color", String(lbl.color ?? "").trim());
        grid.appendChild(labelEl);
    }
}

export function renderMessages(messages, currentUser) {
    const container = document.getElementById("messages");
    container.innerHTML = "";

    messages.forEach(msg => {
        const { user, text } = msg;

        // Decide message type and CSS classes
        let divClass, containerClass;
        if (user === "system") {
            divClass = "system-message";
            containerClass = "d-flex flex-row";
        } else if (user === currentUser) {
            divClass = "self-message";
            containerClass = "d-flex flex-row-reverse";
        } else {
            divClass = "other-message";
            containerClass = "d-flex flex-row";
        }

        // Build message DOM
        const outerDiv = document.createElement("div");
        outerDiv.className = containerClass;

        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${divClass}`;
        msgDiv.textContent = text;

        outerDiv.appendChild(msgDiv);
        container.appendChild(outerDiv);
    });

    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
}


export function collectLabels() {
    const container = document.getElementById("current-labels");
    const boxes = container.querySelectorAll("input[type='checkbox']");
    let selected = [];
    boxes.forEach(box => {
        if (box.checked) {
            selected.push(box.id);
        }
    });

    return JSON.stringify(selected);
}

export function renderExample(data) {
    const exampleField = document.getElementById("current-example");
    exampleField.innerHTML = data;
}

export function lockButtons() {
    const saveDoneButton = document.getElementById("save-done");
    saveDoneButton.disabled = true;
    saveDoneButton.checked = true;

    const container = document.getElementById("current-labels");
    let boxes = container.querySelectorAll("input");
    boxes.forEach(box => {
        box.disabled = true;
    })
}

export function unlockSaveDone() {
    const saveDoneButton = document.getElementById("save-done");
    saveDoneButton.disabled = false;
    saveDoneButton.checked = false;
}
