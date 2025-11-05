export function renderOnlineStatus(online_users) {
    const exampleField = document.getElementById("n-online-status");
    const count = Array.isArray(online_users) ? online_users.length : 0;
    exampleField.innerText = count;
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
