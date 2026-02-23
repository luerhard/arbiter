export function userPicker(name, initialUsers = []) {
    const normalizedUsers = (initialUsers || [])
        .map((u) => ({
            id: Number(u.id),
            username: u.username,
        }))
        .filter((u) => !Number.isNaN(u.id));

    return {
        name,
        query: "",
        open: false,
        selectedUsers: normalizedUsers,

        // Derived data (not stored separately)
        get selectedIds() {
            return this.selectedUsers.map((u) => u.id);
        },

        add(user) {
            const id = Number(user.id);
            if (Number.isNaN(id)) return;

            const exists = this.selectedUsers.some((u) => u.id === id);
            if (!exists) {
                this.selectedUsers.push({ id, username: user.username });
            }

            this.query = "";
            this.open = false;
        },

        remove(id) {
            id = Number(id);
            this.selectedUsers = this.selectedUsers.filter((u) => u.id !== id);
        },
    };
}
