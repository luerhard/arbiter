export function userPicker(name, initialIds) {
    return {
        name,
        query: "",
        open: false,
        selectedIds: (initialIds || []).map(Number),
        selectedUsers: [],
        add(user) {
            const id = Number(user.id);
            if (!this.selectedIds.includes(id)) {
                this.selectedIds.push(id);
                this.selectedUsers.push({ id, username: user.username });
            }
            this.query = "";
            this.open = false;
        },
        remove(id) {
            id = Number(id);
            this.selectedIds = this.selectedIds.filter((x) => x !== id);
            this.selectedUsers = this.selectedUsers.filter((x) => Number(x.id) !== id);
        },
    };
}
