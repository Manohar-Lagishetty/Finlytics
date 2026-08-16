// Cursor-tracked spotlight glow for ".spotlight-card" elements. Sets --x/--y
// (percentages) on pointermove so the card's ::before radial-gradient (see
// styles.css) follows the cursor. Event-delegated on the document so cards
// added/shown later by Alpine need no re-binding.
(function () {
  document.addEventListener("pointermove", (e) => {
    const card = e.target.closest(".spotlight-card");
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    card.style.setProperty("--x", `${x}%`);
    card.style.setProperty("--y", `${y}%`);
  });
})();
