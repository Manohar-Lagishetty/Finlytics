// Dashboard analytics charts (Chart.js). Reads data the view already
// aggregated (json_script blocks), picks a light/dark color set based on
// the current theme, and re-themes in place on the app's "themechange"
// event (see theme.js) rather than reloading the page.
(function () {
  function isDark() {
    return document.documentElement.classList.contains("dark");
  }

  function readJSON(id) {
    const el = document.getElementById(id);
    return el ? JSON.parse(el.textContent) : null;
  }

  const palette = {
    light: { grid: "#e2e8f0", tick: "#94a3b8", line: "#6366f1", fill: "rgba(99, 102, 241, 0.10)", tooltipBg: "#0f172a", tooltipText: "#f8fafc" },
    dark: { grid: "#1e293b", tick: "#64748b", line: "#818cf8", fill: "rgba(129, 140, 248, 0.14)", tooltipBg: "#f8fafc", tooltipText: "#0f172a" },
  };

  function theme() {
    return isDark() ? palette.dark : palette.light;
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (typeof Chart === "undefined") return;
    Chart.defaults.font.family = "Inter, ui-sans-serif, system-ui, sans-serif";

    let trendChart = null;
    let breakdownChart = null;

    const trend = readJSON("trend-data");
    const trendCanvas = document.getElementById("trend-chart");
    if (trend && trendCanvas) {
      const t = theme();
      trendChart = new Chart(trendCanvas, {
        type: "line",
        data: {
          labels: trend.labels,
          datasets: [
            {
              data: trend.values,
              borderColor: t.line,
              backgroundColor: t.fill,
              fill: true,
              borderWidth: 2,
              pointRadius: 0,
              pointHoverRadius: 5,
              pointHoverBackgroundColor: t.line,
              pointHitRadius: 12,
              tension: 0.3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          animation: { duration: 1000, easing: "easeOutQuart" },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: t.tooltipBg,
              titleColor: t.tooltipText,
              bodyColor: t.tooltipText,
              padding: 10,
              cornerRadius: 8,
              displayColors: false,
              callbacks: { label: (ctx) => ctx.parsed.y.toFixed(2) },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { color: t.tick, maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
            y: { beginAtZero: true, grid: { color: t.grid }, border: { display: false }, ticks: { color: t.tick } },
          },
        },
      });
    }

    const categories = readJSON("category-chart-data");
    const breakdownCanvas = document.getElementById("breakdown-chart");
    if (categories && categories.length && breakdownCanvas) {
      const dark = isDark();
      breakdownChart = new Chart(breakdownCanvas, {
        type: "doughnut",
        data: {
          labels: categories.map((c) => c.name),
          datasets: [
            {
              data: categories.map((c) => c.pct),
              backgroundColor: categories.map((c) => (dark ? c.color_dark : c.color_light)),
              borderColor: dark ? "#0f172a" : "#ffffff",
              borderWidth: 2,
              hoverOffset: 10,
              hoverBorderWidth: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: "68%",
          animation: { duration: 1100, easing: "easeOutQuart", animateRotate: true, animateScale: true },
          hover: { mode: "nearest" },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: theme().tooltipBg,
              titleColor: theme().tooltipText,
              bodyColor: theme().tooltipText,
              padding: 10,
              cornerRadius: 8,
              callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed}%` },
            },
          },
        },
      });
    }

    document.addEventListener("themechange", () => {
      const t = theme();

      if (trendChart) {
        trendChart.data.datasets[0].borderColor = t.line;
        trendChart.data.datasets[0].backgroundColor = t.fill;
        trendChart.data.datasets[0].pointHoverBackgroundColor = t.line;
        trendChart.options.plugins.tooltip.backgroundColor = t.tooltipBg;
        trendChart.options.plugins.tooltip.titleColor = t.tooltipText;
        trendChart.options.plugins.tooltip.bodyColor = t.tooltipText;
        trendChart.options.scales.x.ticks.color = t.tick;
        trendChart.options.scales.y.ticks.color = t.tick;
        trendChart.options.scales.y.grid.color = t.grid;
        trendChart.update();
      }

      if (breakdownChart) {
        const dark = isDark();
        breakdownChart.data.datasets[0].backgroundColor = categories.map((c) => (dark ? c.color_dark : c.color_light));
        breakdownChart.data.datasets[0].borderColor = dark ? "#0f172a" : "#ffffff";
        breakdownChart.options.plugins.tooltip.backgroundColor = t.tooltipBg;
        breakdownChart.options.plugins.tooltip.titleColor = t.tooltipText;
        breakdownChart.options.plugins.tooltip.bodyColor = t.tooltipText;
        breakdownChart.update();
      }
    });
  });
})();
