

export function notification() {
    return {
        timer: null,
        init() {
            this.timer = setTimeout(() => {
                this.clear()
            }, 3000);
        },
        clear() {
            this.$refs.renderedNotification.parentNode.removeChild(this.$refs.renderedNotification);
        },
        // Component destructor
        destroy() {
            clearInterval(this.timer);
        },
    };
};

export function notify(header, icon="check-circle") {
    if (window.notifiable === undefined) {
        window.notifiable = true;
        try {
            window.notifyArea = document.getElementById('notification-area');
            window.notifyTemplate = document.getElementById('notification');
            window.checkCircle = document.getElementById('check-circle');
            window.xCircle = document.getElementById('x-circle');
            window.arrowUpCircle = document.getElementById('arrow-up-circle');
        } catch(e) {
            console.log("This webpage is missing the Cotton Notification template.");
            window.notifiable = false;
        };
    };

    if (!notifiable) return;

    const clone = document.importNode(notifyTemplate.content, true);
    if (icon == "x-circle")
        clone.getElementById('notifyIcon').appendChild(document.importNode(xCircle.content, true));
    else if (icon == "check-circle")
        clone.getElementById('notifyIcon').appendChild(document.importNode(checkCircle.content, true));
    else if (icon == "arrow-up-circle")
        clone.getElementById('notifyIcon').appendChild(document.importNode(arrowUpCircle.content, true));
    clone.getElementById('notifyHead').textContent = header;
    notifyArea.appendChild(clone);
};