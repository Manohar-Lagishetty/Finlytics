// Expense list page: instant client-side column show/hide (persisted to
// the server in the background) plus the delete-confirmation modal state.
function expenseList({ hiddenInitial, updateColumnsUrl, csrfToken }) {
  return {
    hidden: [...hiddenInitial],
    columnsOpen: false,
    confirmId: null,
    confirmLabel: "",

    isHidden(col) {
      return this.hidden.includes(col);
    },

    async toggleColumn(col) {
      this.hidden = this.isHidden(col) ? this.hidden.filter((c) => c !== col) : [...this.hidden, col];
      const body = new URLSearchParams();
      this.hidden.forEach((c) => body.append("hidden", c));
      await fetch(updateColumnsUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
    },

    confirmDelete(id, label) {
      this.confirmId = id;
      this.confirmLabel = label;
    },
  };
}
