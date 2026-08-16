// Dark / light theme toggle. The initial class is already set synchronously
// in <head> (see base.html) to avoid a flash of the wrong theme.
(function () {
  const STORAGE_KEY = "finlytics-theme";

  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function applyIcons() {
    document.querySelectorAll("[data-theme-icon]").forEach((el) => {
      const wantsDark = el.getAttribute("data-theme-icon") === "dark";
      el.classList.toggle("hidden", wantsDark !== isDark());
    });
  }

  window.toggleTheme = function () {
    document.documentElement.classList.toggle("dark");
    localStorage.setItem(STORAGE_KEY, isDark() ? "dark" : "light");
    applyIcons();
    document.dispatchEvent(new CustomEvent("themechange", { detail: { dark: isDark() } }));
  };

  document.addEventListener("DOMContentLoaded", applyIcons);
})();
