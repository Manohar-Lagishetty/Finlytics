// Expense list page: instant client-side column show/hide (persisted to
// the server in the background), row selection for bulk delete, and the
// delete-confirmation modal state (single row or the whole selection).
function expenseList({ hiddenInitial, updateColumnsUrl, csrfToken, totalCount }) {
  return {
    hidden: [...hiddenInitial],
    columnsOpen: false,
    confirmId: null,
    confirmLabel: "",
    confirmBulk: false,
    // Selected expense ids, as strings (checkbox values). Scoped to the
    // current page — navigating away resets it.
    selected: [],
    // True once the user opts into "select all N matching expenses": the
    // delete then applies to every expense matching the current filters,
    // across all pages, not just the ids ticked here.
    selectAllMatching: false,
    totalCount,

    init() {
      // Unticking any row drops back out of select-all-matching mode.
      this.$watch("selected", () => {
        if (this.selectAllMatching && !this.allSelected) this.selectAllMatching = false;
      });
    },

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

    get pageIds() {
      return [...this.$root.querySelectorAll("[data-row-select]")].map((el) => el.value);
    },

    get allSelected() {
      const ids = this.pageIds;
      return ids.length > 0 && ids.every((id) => this.selected.includes(id));
    },

    get someSelected() {
      return this.selected.length > 0 && !this.allSelected;
    },

    isSelected(id) {
      return this.selected.includes(String(id));
    },

    get selectedCount() {
      return this.selectAllMatching ? this.totalCount : this.selected.length;
    },

    // Offer the cross-page option only when the whole page is ticked and
    // there are more matching expenses than this page shows.
    get canSelectAllMatching() {
      return this.allSelected && this.totalCount > this.pageIds.length;
    },

    toggleAll(checked) {
      this.selected = checked ? this.pageIds : [];
    },

    clearSelection() {
      this.selected = [];
      this.selectAllMatching = false;
    },

    get confirmOpen() {
      return this.confirmId !== null || this.confirmBulk;
    },

    confirmDelete(id, label) {
      this.confirmId = id;
      this.confirmLabel = label;
    },

    confirmBulkDelete() {
      if (this.selected.length) this.confirmBulk = true;
    },

    closeConfirm() {
      this.confirmId = null;
      this.confirmBulk = false;
    },

    submitConfirm() {
      const formId = this.confirmBulk ? "bulk-delete-form" : "delete-expense-form-" + this.confirmId;
      document.getElementById(formId).submit();
      this.closeConfirm();
    },
  };
}
