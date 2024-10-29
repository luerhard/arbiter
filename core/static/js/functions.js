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


export function inferTextColorByContrast(color) {
    // Calculate luminance of the color
    const rgb = parseInt(color.slice(1), 16);
    const r = (rgb >> 16) & 0xff;
    const g = (rgb >> 8) & 0xff;
    const b = (rgb >> 0) & 0xff;
    const luminance = 0.2126 * r / 255 + 0.7152 * g / 255 + 0.0722 * b / 255;
    const textColor = luminance > 0.5 ? 'black' : 'white';
    return textColor;
}
