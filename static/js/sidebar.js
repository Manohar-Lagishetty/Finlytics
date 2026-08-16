// Collapsible sidebar. Width + label visibility persisted across reloads.
(function () {
  const STORAGE_KEY = "finlytics-sidebar-collapsed";
  const EXPANDED = "w-64";
  const COLLAPSED = "w-20";

  function sidebar() {
    return document.getElementById("app-sidebar");
  }

  function setCollapsed(collapsed) {
    const el = sidebar();
    if (!el) return;

    el.classList.toggle(EXPANDED, !collapsed);
    el.classList.toggle(COLLAPSED, collapsed);

    document.querySelectorAll(".nav-label, [data-sidebar-label]").forEach((label) => {
      label.classList.toggle("hidden", collapsed);
    });
    document.querySelectorAll("[data-sidebar-collapse-icon]").forEach((icon) => {
      icon.classList.toggle("rotate-180", collapsed);
    });
    document.querySelectorAll("[data-sidebar-only-collapsed]").forEach((el2) => {
      el2.classList.toggle("hidden", !collapsed);
    });

    localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
  }

  window.toggleSidebar = function () {
    const el = sidebar();
    if (!el) return;
    setCollapsed(el.classList.contains(EXPANDED));
  };

  document.addEventListener("DOMContentLoaded", function () {
    setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
  });
})();
