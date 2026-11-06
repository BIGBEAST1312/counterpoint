// Sign-in background: 3D queue tickets drifting toward the viewer, like a queue moving up.
// Move the mouse to look around (closer tickets move more), tickets move out of the cursor's way,
// and a click sends a ripple through them. No library. Colours come from --accent, so every theme works.
// Stops when the sign-in screen is hidden or the tab is in the background, and stays still for reduced motion.
(() => {
  const section = document.getElementById("v-login");
  if (!section || !window.CanvasRenderingContext2D) return;

  const canvas = document.createElement("canvas");
  canvas.className = "login-bg";
  canvas.setAttribute("aria-hidden", "true");
  section.prepend(canvas);
  section.classList.add("has-3d");
  const ctx = canvas.getContext("2d");

  const still = matchMedia("(prefers-reduced-motion: reduce)");
  const NEAR = 1.2, FAR = 9, W = 150, H = 76;   // ticket size in its own units
  let w = 0, h = 0, focal = 1, tickets = [], color = "#1E5E43", frame = 0, last = 0;
  const pointer = { x: 0, y: 0, tx: 0, ty: 0, sx: -1e4, sy: -1e4 };
  const rand = (a, b) => a + Math.random() * (b - a);

  function spawn(t, anyDepth) {
    t.z = anyDepth ? rand(NEAR + 0.5, FAR) : FAR;
    const spread = anyDepth ? 0.6 : 0.38;   // far ones start nearer the middle, so they come toward you instead of drifting off the edge
    t.x = rand(-1, 1) * t.z * (w / focal) * spread;
    t.y = rand(-1, 1) * t.z * (h / focal) * spread;
    t.vx = t.vy = 0; t.age = 0;
    t.rx = rand(-0.6, 0.6); t.ry = rand(-0.9, 0.9); t.rz = rand(-0.5, 0.5);
    t.sx = rand(-0.15, 0.15); t.sy = rand(-0.25, 0.25); t.sz = rand(-0.1, 0.1);
    t.label = "#" + String(Math.floor(rand(1, 99))).padStart(3, "0");
    return t;
  }

  function resize() {
    const r = section.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    w = r.width; h = r.height; focal = Math.min(w, h) * 0.9;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const want = Math.max(16, Math.min(60, Math.round((w * h) / 22000)));
    while (tickets.length < want) tickets.push(spawn({}, true));
    tickets.length = want;
  }

  function readColor() {
    color = getComputedStyle(section).getPropertyValue("--accent").trim() || color;
  }

  function ticketPath() {   // ticket outline with a notch on each side, in its own units
    const x = -W / 2, y = -H / 2, r = 9, n = 10;
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.lineTo(x + W - r, y); ctx.arcTo(x + W, y, x + W, y + r, r);
    ctx.lineTo(x + W, -n); ctx.arc(x + W, 0, n, -Math.PI / 2, Math.PI / 2, true);
    ctx.lineTo(x + W, y + H - r); ctx.arcTo(x + W, y + H, x + W - r, y + H, r);
    ctx.lineTo(x + r, y + H); ctx.arcTo(x, y + H, x, y + H - r, r);
    ctx.lineTo(x, n); ctx.arc(x, 0, n, Math.PI / 2, -Math.PI / 2, true);
    ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  function step(dt) {
    pointer.x += (pointer.tx - pointer.x) * Math.min(1, dt * 3);
    pointer.y += (pointer.ty - pointer.y) * Math.min(1, dt * 3);
    for (const t of tickets) {
      t.z -= dt * 0.55; t.age += dt;
      if (t.z < NEAR) spawn(t, false);
      t.rx += t.sx * dt; t.ry += t.sy * dt; t.rz += t.sz * dt;
      // Move out of the cursor's way.
      const s = focal / t.z, px = w / 2 + (t.x - pointer.x * 0.9) * s, py = h / 2 + (t.y - pointer.y * 0.6) * s;
      const dx = px - pointer.sx, dy = py - pointer.sy, d2 = dx * dx + dy * dy, R = 150;
      if (d2 < R * R) {
        const d = Math.sqrt(d2) || 1, push = (1 - d / R) * 1.2 / s;
        t.vx += (dx / d) * push * 60 * dt; t.vy += (dy / d) * push * 60 * dt;
        t.sy += (1 - d / R) * dt * 0.8;
      }
      t.x += t.vx * dt * 60; t.y += t.vy * dt * 60;
      t.vx *= Math.pow(0.04, dt); t.vy *= Math.pow(0.04, dt);
      if (Math.abs(t.x) > t.z * (w / focal) * 0.75 + 1 || Math.abs(t.y) > t.z * (h / focal) * 0.75 + 1) spawn(t, true);   // pushed out of view: fades back in somewhere else
      t.sy += (Math.sign(t.sy || 1) * 0.15 - t.sy) * Math.min(1, dt * 1.5);   // spin settles back down
    }
  }

  function draw() {
    ctx.setTransform(canvas.width / w, 0, 0, canvas.height / h, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = ctx.fillStyle = color;
    ctx.lineJoin = "round";
    tickets.sort((a, b) => b.z - a.z);   // far ones first
    const base = canvas.width / w;
    for (const t of tickets) {
      const s = focal / t.z / W * 1.1;
      const cx = w / 2 + (t.x - pointer.x * 0.9) * (focal / t.z);
      const cy = h / 2 + (t.y - pointer.y * 0.6) * (focal / t.z);
      // Turn the ticket in 3D and flatten it onto the screen.
      const cX = Math.cos(t.rx), sX = Math.sin(t.rx), cY = Math.cos(t.ry), sY = Math.sin(t.ry), cZ = Math.cos(t.rz), sZ = Math.sin(t.rz);
      const ux = cY * cZ, uy = cX * sZ + sX * sY * cZ, uz = sX * sZ - cX * sY * cZ;
      const vx = -cY * sZ, vy = cX * cZ - sX * sY * sZ, vz = sX * cZ + cX * sY * sZ;
      const nz = ux * vy - uy * vx;   // which way it faces
      const fog = Math.min(1, (FAR - t.z) / 2.5) * Math.min(1, (t.z - NEAR) / 1.8) * Math.min(1, t.age / 0.8);
      const light = 0.55 + 0.45 * Math.abs(nz) + 0.15 * (uz + vz);
      ctx.setTransform(ux * s * base, uy * s * base, vx * s * base, vy * s * base, cx * base, cy * base);
      ticketPath();
      ctx.globalAlpha = fog * 0.07 * light; ctx.fill();
      ctx.globalAlpha = fog * 0.28 * light; ctx.lineWidth = 2.2; ctx.stroke();
      ctx.beginPath(); ctx.setLineDash([4, 5]); ctx.moveTo(-W / 2 + 36, -H / 2 + 8); ctx.lineTo(-W / 2 + 36, H / 2 - 8); ctx.stroke(); ctx.setLineDash([]);
      if (nz > 0) {   // only the front shows the number
        ctx.font = "700 26px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.globalAlpha = fog * 0.34 * light; ctx.fillText(t.label, 18, 1);
      }
    }
    ctx.globalAlpha = 1;
  }

  function loop(now) {
    const dt = Math.min(0.05, (now - (last || now)) / 1000); last = now;
    step(dt); draw();
    frame = requestAnimationFrame(loop);
  }

  function start() {
    cancelAnimationFrame(frame); frame = 0; last = 0;
    if (section.hidden || document.hidden) return;
    readColor(); resize();
    if (still.matches) draw(); else frame = requestAnimationFrame(loop);
  }

  section.addEventListener("pointermove", (e) => {
    const r = section.getBoundingClientRect();
    pointer.sx = e.clientX - r.left; pointer.sy = e.clientY - r.top;
    pointer.tx = (pointer.sx / r.width - 0.5) * 2; pointer.ty = (pointer.sy / r.height - 0.5) * 2;
  });
  section.addEventListener("pointerleave", () => { pointer.sx = pointer.sy = -1e4; pointer.tx = pointer.ty = 0; });
  section.addEventListener("pointerdown", (e) => {   // ripple: push nearby tickets away and spin them
    if (e.target.closest("form, a, button, input")) return;
    for (const t of tickets) { const k = 0.02 * t.z; t.vx += rand(-1, 1) * k; t.vy += rand(-1, 1) * k; t.sy += rand(0.6, 1.4) * (Math.random() < 0.5 ? -1 : 1); }
  });

  new MutationObserver(start).observe(section, { attributes: true, attributeFilter: ["hidden"] });
  new MutationObserver(() => { readColor(); if (still.matches) draw(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-accent"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readColor(); if (still.matches) draw(); });
  still.addEventListener("change", start);
  document.addEventListener("visibilitychange", start);
  new ResizeObserver(() => { if (!section.hidden) { resize(); if (still.matches) draw(); } }).observe(section);
  start();
})();
