export function collectLabels(containerLabel) {
    const container = document.getElementById(containerLabel);
    const boxes = container.querySelectorAll("input[type='checkbox']");
    let selected = new Map();
    boxes.forEach(box => {
        selected[box.id] = Number(box.checked);
    });

    return JSON.stringify(selected);
}

export function unlockButton(buttonLabel) {
    const button = document.getElementById(buttonLabel);
    button.disabled = false;
    button.checked = false;
}
