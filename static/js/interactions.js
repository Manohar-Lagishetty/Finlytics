// Shared micro-interactions used across the whole app shell:
//  - ripple: click feedback on any ".ripple-container" (event-delegated,
//    so it works for content Alpine adds/shows later without rebinding)
//  - count-up: numbers in [data-count-up] animate from 0 to their
//    server-rendered value on load (degrades gracefully with JS off,
//    since the SSR'd text is already the correct final value)
//  - scroll-reveal: [data-reveal] elements fade/rise in the first time
//    they enter the viewport
(function () {
  document.addEventListener("click", (e) => {
    const container = e.target.closest(".ripple-container");
    if (!container) return;

    const rect = container.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 1.6;
    const span = document.createElement("span");
    span.className = "ripple";
    span.style.width = span.style.height = `${size}px`;
    span.style.left = `${e.clientX - rect.left - size / 2}px`;
    span.style.top = `${e.clientY - rect.top - size / 2}px`;
    container.appendChild(span);
    span.addEventListener("animationend", () => span.remove());
  });

  function animateCountUp(el) {
    const decimals = parseInt(el.dataset.countDecimals || "2", 10);
    const raw = (el.textContent || "0").replace(/,/g, "").trim();
    const target = parseFloat(raw);
    if (Number.isNaN(target)) return;

    const duration = 900;
    const start = performance.now();
    el.textContent = (0).toFixed(decimals);

    function tick(now) {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
      el.textContent = (target * eased).toFixed(decimals);
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = target.toFixed(decimals);
      }
    }
    requestAnimationFrame(tick);
  }

  const revealObserver =
    "IntersectionObserver" in window
      ? new IntersectionObserver(
          (entries) => {
            entries.forEach((entry) => {
              if (entry.isIntersecting) {
                entry.target.classList.add("revealed");
                revealObserver.unobserve(entry.target);
              }
            });
          },
          { threshold: 0.12 }
        )
      : null;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-count-up]").forEach(animateCountUp);

    if (revealObserver) {
      document.querySelectorAll("[data-reveal]").forEach((el) => revealObserver.observe(el));
    } else {
      document.querySelectorAll("[data-reveal]").forEach((el) => el.classList.add("revealed"));
    }
  });
})();
