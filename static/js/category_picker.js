// Cascading category picker: each level is a <select> of one category's
// children. Picking a value fetches its children and, if any exist,
// appends the next level. Any level can also create a brand-new
// category/subcategory inline via the categories/create/ endpoint.
//
// Also doubles as the whole expense form's root x-data (submitting state,
// the typed amount, and a live budget-status preview) so the category
// picker and the budget banner can share one reactive scope.
function categoryPicker({
  rootCategories,
  childrenUrl,
  createUrl,
  csrfToken,
  initialPathIds = [],
  budgetStatusUrlTemplate = null,
  initialAmount = 0,
}) {
  return {
    levels: [{ options: rootCategories, selectedId: "", adding: false, newName: "", error: "", creating: false }],
    selectedCategoryId: "",
    loadingChildren: false,
    submitting: false,
    // x-model on the amount input syncs data -> DOM on load, so this must
    // start at the field's actual current value (edit prefill / a
    // re-rendered validation error), never a hardcoded 0.
    amountValue: initialAmount,
    budgetStatus: null,
    budgetLoading: false,

    async init() {
      // Pre-populate the cascading dropdowns for an already-selected
      // category (editing an existing expense, or re-rendering after a
      // validation error on another field).
      for (const id of initialPathIds) {
        await this.choose(this.levels.length - 1, String(id));
      }
    },

    get selectedPath() {
      return this.levels
        .filter((level) => level.selectedId)
        .map((level) => level.options.find((o) => String(o.id) === String(level.selectedId))?.name)
        .filter(Boolean)
        .join(" › ");
    },

    get budgetPreview() {
      if (!this.budgetStatus || !this.budgetStatus.has_budget) return null;
      const cap = parseFloat(this.budgetStatus.cap) || 0;
      const spent = parseFloat(this.budgetStatus.spent) || 0;
      const projected = spent + (parseFloat(this.amountValue) || 0);
      return {
        categoryName: this.budgetStatus.category_name,
        cap,
        spent,
        projected,
        pct: cap ? Math.round((projected / cap) * 1000) / 10 : 0,
      };
    },

    async choose(levelIndex, id) {
      this.levels[levelIndex].selectedId = id;
      this.levels[levelIndex].adding = false;
      this.levels = this.levels.slice(0, levelIndex + 1);
      this.selectedCategoryId = id || "";
      if (!id) {
        this.budgetStatus = null;
        return;
      }
      await Promise.all([this.loadChildren(levelIndex, id), this.fetchBudgetStatus(id)]);
    },

    async loadChildren(levelIndex, parentId) {
      this.loadingChildren = true;
      try {
        const res = await fetch(`${childrenUrl}?parent_id=${encodeURIComponent(parentId)}`);
        const data = await res.json();
        if (data.children && data.children.length) {
          this.levels.push({ options: data.children, selectedId: "", adding: false, newName: "", error: "", creating: false });
        }
      } finally {
        this.loadingChildren = false;
      }
    },

    async fetchBudgetStatus(categoryId) {
      if (!budgetStatusUrlTemplate) return;
      this.budgetLoading = true;
      try {
        const res = await fetch(budgetStatusUrlTemplate.replace("0", categoryId));
        this.budgetStatus = await res.json();
      } finally {
        this.budgetLoading = false;
      }
    },

    toggleAdd(levelIndex) {
      const level = this.levels[levelIndex];
      level.adding = !level.adding;
      level.error = "";
      level.newName = "";
    },

    async createCategory(levelIndex) {
      const level = this.levels[levelIndex];
      const name = level.newName.trim();
      if (!name) {
        level.error = "Enter a name.";
        return;
      }
      const parentId = levelIndex === 0 ? "" : this.levels[levelIndex - 1].selectedId;
      const body = new URLSearchParams({ name, parent_id: parentId || "" });

      level.creating = true;
      level.error = "";
      try {
        const res = await fetch(createUrl, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken, "Content-Type": "application/x-www-form-urlencoded" },
          body,
        });
        const data = await res.json();

        if (!res.ok) {
          level.error = data.error || "Could not create category.";
          return;
        }

        level.options.push({ id: data.id, name: data.name });
        level.options.sort((a, b) => a.name.localeCompare(b.name));
        await this.choose(levelIndex, String(data.id));
      } finally {
        level.creating = false;
      }
    },
  };
}
