export function updatePrevLabels(data) {
    const container = document.getElementById("prev-labels");
    container.innerHTML = "";
    let mytitleText;
    let mybuttonDiv;
    for (const [username, labels] of Object.entries(data["update-labels"])) {
        let textDiv = document.createElement("div");
        textDiv.className = "my-3";
        container.appendChild(textDiv);

        let titleText = document.createElement("p");
        titleText.className = "d-flex mt-3 mb-3 text-muted"
        if (username == data["current-user"]) {
            // save own title text to buffer
            titleText.innerHTML = "Your previous annotations:";
            mytitleText = titleText;
        } else {
            titleText.innerHTML = `Previous annotations of ${username}:`
            textDiv.appendChild(titleText);
        }


        let buttonDiv = document.createElement("div");
        buttonDiv.className = "btn-group d-flex flex-wrap";

        labels.forEach(label => {
            let button = document.createElement("button");
            button.disabled = true;
            if (label["is_set"]) {
                button.className = "btn btn-primary";
            } else {
                button.className = "btn btn-outline-primary";
            }
            button.innerHTML = label["label"];
            buttonDiv.appendChild(button);

        })
        if (username == data["current-user"]) {
            // save own title text to buffer
            mybuttonDiv = buttonDiv;
        } else {
            container.appendChild(buttonDiv);

        }
    }
    // insert own previous annotations last;
    container.appendChild(mytitleText);
    container.appendChild(mybuttonDiv);

}



export function updateCurrentLabels(data) {
    const container = document.getElementById("current-labels");
    container.innerHTML = "";
    let titleText = document.createElement("p");
    titleText.className = "mt-3 mb-3 text-muted";
    titleText.innerHTML = "Your revised annotation:";
    container.appendChild(titleText);

    let buttonGroup = document.createElement("div");
    buttonGroup.className = "btn-group d-flex flex-wrap";
    container.appendChild(buttonGroup);
    const user = data["current-user"];
    data["update-labels"][user].forEach(label => {
        let checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "btn-check";
        checkbox.id = label["id"];
        checkbox.name = "label_" + label["id"];
        buttonGroup.appendChild(checkbox);

        let checkboxLabel = document.createElement("label");
        checkboxLabel.innerHTML = label["label"];
        checkboxLabel.htmlFor = label["id"];
        checkboxLabel.className = "btn btn-outline-primary";
        buttonGroup.appendChild(checkboxLabel)

        if (label["is_set"] == true) {
            checkbox.checked = true;
        } else {
            checkbox.checked = false;
        }
    })
}

export function collectLabels() {
    const container = document.getElementById("current-labels");
    const boxes = container.querySelectorAll("input[type='checkbox']");
    let selected = new Map();
    boxes.forEach(box => {
        selected[box.id] = Number(box.checked);
    });

    return JSON.stringify(selected);
}

export function updateSentence(data) {
    const sentenceField = document.getElementById("current-sentence");
    sentenceField.innerHTML = data["update-sentence"];
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
