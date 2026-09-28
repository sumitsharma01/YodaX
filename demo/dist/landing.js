// An original flowing signal field, drawn locally without external assets.
(() => {
  const canvas = document.getElementById("signal-canvas");
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  let width = 0,
    height = 0,
    frame = 0,
    visible = true;
  const motion = { x: 0, y: 0, hover: 0 };
  const target = { x: 0, y: 0, hover: 0 };
  function resetPointer() { target.x = target.y = target.hover = 0; }
  function resize() {
    const rect = canvas.getBoundingClientRect();
    width = rect.width;
    height = rect.height;
    const scale = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    if (reduced.matches) draw(0);
  }
  function point(t, strand, time) {
    const phase = t * Math.PI * 4.4 + time * 0.18;
    const twist = strand * 0.14 + phase;
    const envelope = 0.55 + 0.45 * Math.sin(t * Math.PI);
    const centre =
      width * (0.49 + 0.21 * Math.sin(t * Math.PI * 3.6 + time * 0.1));
    const ribbon = width * 0.21 * envelope;
    const base = {
      x:
        centre +
        Math.cos(twist) * ribbon +
        Math.sin(t * 6 + strand * 0.05) * width * 0.05 +
        0,
      y: height * (0.07 + t * 0.85) + Math.sin(twist) * height * 0.06,
      z: (Math.sin(twist) + 1) / 2,
    };
    // Rotate the ribbon in depth toward the cursor, then project onto the canvas.
    const zoom = 1 + motion.hover * 0.16;
    const x = (base.x - width / 2) * zoom;
    const y = (base.y - height / 2) * zoom;
    const z = (base.z - 0.5) * width * 0.32;
    const yaw = motion.x * 0.28, pitch = -motion.y * 0.22;
    const rx = x * Math.cos(yaw) + z * Math.sin(yaw);
    const rz = -x * Math.sin(yaw) + z * Math.cos(yaw);
    const ry = y * Math.cos(pitch) - rz * Math.sin(pitch);
    const depth = y * Math.sin(pitch) + rz * Math.cos(pitch);
    const perspective = 1 / (1 - depth / Math.max(width * 2, 1));
    return {
      x: width / 2 + rx * perspective + motion.x * 12,
      y: height / 2 + ry * perspective + motion.y * 10,
      z: base.z,
    };
  }
  function draw(time) {
    ctx.clearRect(0, 0, width, height);
    for (const key of ["x", "y", "hover"]) {
      motion[key] += (target[key] - motion[key]) * 0.1;
    }
    for (let strand = 0; strand < 44; strand++) {
      ctx.beginPath();
      for (let i = 0; i <= 110; i++) {
        const p = point(i / 110, strand, time);
        if (!i) ctx.moveTo(p.x, p.y);
        else ctx.lineTo(p.x, p.y);
      }
      ctx.strokeStyle = `rgba(163, 170, 143, ${0.035 + (strand % 7) * 0.009})`;
      ctx.lineWidth = 0.65;
      ctx.stroke();
      for (let dot = 0; dot < 8; dot++) {
        const t = (dot / 8 + strand * 0.021 + time * 0.014) % 1;
        const p = point(t, strand, time);
        const alpha = (0.12 + p.z * 0.55) * Math.sin(t * Math.PI);
        const radius = (0.45 + p.z * 1.1) * (1 + motion.hover * 1.15);
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(226, 229, 207, ${alpha})`;
        ctx.fill();
        if (strand % 11 === 0 && p.z > 0.8) {
          const glow = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 6);
          glow.addColorStop(0, `rgba(219, 226, 189, ${alpha * 0.3})`);
          glow.addColorStop(1, "rgba(219,226,189,0)");
          ctx.fillStyle = glow;
          ctx.fillRect(p.x - 6, p.y - 6, 12, 12);
        }
      }
    }
  }
  let last = 0;
  function animate(timestamp) {
    if (visible && !document.hidden && timestamp - last > 32) {
      draw(timestamp / 1000);
      last = timestamp;
    }
    frame = requestAnimationFrame(animate);
  }
  function start() {
    cancelAnimationFrame(frame);
    if (reduced.matches) { resetPointer(); motion.x = motion.y = motion.hover = 0; draw(0); }
    else frame = requestAnimationFrame(animate);
  }
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting;
  }).observe(canvas);
  const hero = document.querySelector(".hero");
  hero.addEventListener("pointermove", (event) => {
    if (event.pointerType === "touch" || reduced.matches) return;
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) { resetPointer(); return; }
    target.x = x * 2 - 1;
    target.y = y * 2 - 1;
    target.hover = 1;
  });
  hero.addEventListener("pointerleave", resetPointer);
  hero.addEventListener("pointercancel", resetPointer);
  window.addEventListener("blur", resetPointer);
  reduced.addEventListener("change", start);
  resize();
  start();
})();
