// Lightweight CSS-3D tilt effect for elements with the .tilt-card class.
// No dependency — just pointer position -> rotateX/rotateY.
(function () {
  const MAX_TILT = 8;

  function bind(card) {
    const strength = parseFloat(card.dataset.tiltStrength || MAX_TILT);

    card.addEventListener("mousemove", (e) => {
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;

      card.dataset.tiltActive = "true";
      card.style.transform =
        `perspective(1000px) rotateX(${(-y * strength).toFixed(2)}deg) ` +
        `rotateY(${(x * strength).toFixed(2)}deg) translateZ(4px)`;
    });

    card.addEventListener("mouseleave", () => {
      card.dataset.tiltActive = "false";
      card.style.transform = "perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0)";
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".tilt-card").forEach(bind);
  });
})();
