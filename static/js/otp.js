// Six-box OTP input: auto-advance, backspace, paste, expiry + resend countdown.
(function () {
  document.addEventListener("DOMContentLoaded", () => {
    const boxes = Array.from(document.querySelectorAll(".otp-box"));
    const hidden = document.getElementById("otp-hidden");
    const form = document.getElementById("otp-form");
    if (!boxes.length || !hidden) return;

    function sync() {
      hidden.value = boxes.map((b) => b.value).join("");
      boxes.forEach((b) => b.classList.toggle("filled", b.value !== ""));
    }

    boxes.forEach((box, i) => {
      box.addEventListener("input", () => {
        box.value = box.value.replace(/[^0-9]/g, "").slice(-1);
        sync();
        if (box.value && i < boxes.length - 1) boxes[i + 1].focus();
        if (boxes.every((b) => b.value) && form) {
          // Auto-submit once all 6 digits are present.
          form.requestSubmit ? form.requestSubmit() : form.submit();
        }
      });

      box.addEventListener("keydown", (e) => {
        if (e.key === "Backspace" && !box.value && i > 0) {
          boxes[i - 1].focus();
        }
      });

      box.addEventListener("paste", (e) => {
        e.preventDefault();
        const digits = (e.clipboardData.getData("text") || "").replace(/[^0-9]/g, "").split("");
        digits.slice(0, boxes.length).forEach((d, idx) => {
          if (boxes[idx]) boxes[idx].value = d;
        });
        sync();
        const next = boxes[Math.min(digits.length, boxes.length - 1)];
        if (next) next.focus();
      });
    });

    if (boxes[0]) boxes[0].focus();

    // --- Expiry countdown (10 minutes) ---
    const expiryEl = document.getElementById("otp-expiry");
    if (expiryEl) {
      let remaining = 10 * 60;
      const tick = () => {
        const m = Math.floor(remaining / 60).toString().padStart(2, "0");
        const s = Math.floor(remaining % 60).toString().padStart(2, "0");
        expiryEl.textContent = `${m}:${s}`;
        if (remaining <= 0) {
          clearInterval(timer);
          expiryEl.textContent = "expired";
          expiryEl.classList.add("text-rose-500");
        }
        remaining -= 1;
      };
      tick();
      const timer = setInterval(tick, 1000);
    }

    // --- Resend cooldown (30s) ---
    const resendBtn = document.getElementById("resend-otp-btn");
    const resendCountdown = document.getElementById("resend-countdown");
    if (resendBtn) {
      let cooldown = 30;
      resendBtn.disabled = true;
      const tick = () => {
        if (cooldown <= 0) {
          clearInterval(timer);
          resendBtn.disabled = false;
          resendBtn.classList.remove("opacity-50", "cursor-not-allowed");
          if (resendCountdown) resendCountdown.textContent = "";
          return;
        }
        if (resendCountdown) resendCountdown.textContent = `(${cooldown}s)`;
        cooldown -= 1;
      };
      resendBtn.classList.add("opacity-50", "cursor-not-allowed");
      tick();
      const timer = setInterval(tick, 1000);
    }
  });
})();
