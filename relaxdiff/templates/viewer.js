// In-page viewer logic. Reads window.__RELAXDIFF__ payload and drives 3Dmol.js.

(function () {
  const data = window.__RELAXDIFF__;
  if (!data) return;

  const viewer = $3Dmol.createViewer("viewer", { backgroundColor: "#f6f8fa" });

  // Two models: 0 = before, 1 = after (aligned).
  const beforeModel = viewer.addModel(data.before_cif, "cif", { keepH: true });
  const afterModel  = viewer.addModel(data.after_cif,  "cif", { keepH: true });

  const ARROW_BIG   = "#cf222e"; // > 1.0 Å
  const ARROW_MID   = "#bf8700"; // > 0.3 Å
  const ARROW_SMALL = "#0969da"; // smaller

  // ---- displacement-magnitude color spectrum for the Diff mode ----
  // 0 Å → blue, max → red.
  function magnitudeColor(d, dMax) {
    const t = dMax > 1e-6 ? Math.min(1, d / dMax) : 0;
    // Interpolate blue (9,105,218) → orange (191,135,0) → red (207,34,46)
    let r, g, b;
    if (t < 0.5) {
      const u = t / 0.5;
      r = Math.round(9 + (191 - 9) * u);
      g = Math.round(105 + (135 - 105) * u);
      b = Math.round(218 + (0 - 218) * u);
    } else {
      const u = (t - 0.5) / 0.5;
      r = Math.round(191 + (207 - 191) * u);
      g = Math.round(135 + (34 - 135) * u);
      b = Math.round(0 + (46 - 0) * u);
    }
    return `rgb(${r},${g},${b})`;
  }

  const dMax = data.max_displacement || 1.0;

  // Stash displacement on each after-atom for the Diff coloring mode.
  const afterAtomsRaw = afterModel.selectedAtoms({});
  data.displacements.forEach((d) => {
    const a = afterAtomsRaw[d.index];
    if (a) {
      a.properties = a.properties || {};
      a.properties.disp = d.displacement;
      a.properties.dispColor = magnitudeColor(d.displacement, dMax);
    }
  });

  function applyStyle(mode) {
    // mode: "before" | "after" | "overlay" | "diff"
    if (mode === "before") {
      viewer.setStyle({ model: beforeModel }, {
        stick:  { radius: 0.14 },
        sphere: { scale: 0.32 },
      });
      viewer.setStyle({ model: afterModel }, { stick: { hidden: true }, sphere: { hidden: true } });
    } else if (mode === "after") {
      viewer.setStyle({ model: beforeModel }, { stick: { hidden: true }, sphere: { hidden: true } });
      viewer.setStyle({ model: afterModel }, {
        stick:  { radius: 0.14 },
        sphere: { scale: 0.32 },
      });
    } else if (mode === "overlay") {
      // BEFORE = small ghost spheres only, no bonds → reduces visual noise.
      viewer.setStyle({ model: beforeModel }, {
        sphere: { scale: 0.18, opacity: 0.35 },
        stick:  { hidden: true },
      });
      viewer.setStyle({ model: afterModel }, {
        stick:  { radius: 0.14 },
        sphere: { scale: 0.30 },
      });
    } else if (mode === "diff") {
      // Hide before entirely; color after atoms by displacement magnitude.
      // No bonds, so movement signal is dominant.
      viewer.setStyle({ model: beforeModel }, { stick: { hidden: true }, sphere: { hidden: true } });
      viewer.setStyle({ model: afterModel }, { sphere: { scale: 0.34 } });
      const atoms = afterModel.selectedAtoms({});
      atoms.forEach((a) => {
        if (a.properties && a.properties.dispColor) {
          viewer.setStyle({ model: afterModel, serial: a.serial },
                          { sphere: { scale: 0.34, color: a.properties.dispColor } });
        }
      });
    }
    viewer.render();
  }

  function addArrows() {
    viewer.removeAllShapes();
    const top = [...data.displacements]
      .sort((a, b) => b.displacement - a.displacement)
      .slice(0, 24);

    const afterAtoms = afterModel.selectedAtoms({});
    top.forEach((d) => {
      if (d.displacement < 0.05) return;
      const a = afterAtoms[d.index];
      if (!a) return;
      const end = { x: a.x, y: a.y, z: a.z };
      const start = { x: a.x - d.vec[0], y: a.y - d.vec[1], z: a.z - d.vec[2] };
      viewer.addArrow({
        start: start,
        end: end,
        radius: 0.08,
        radiusRatio: 2.2,
        color: d.displacement > 1.0 ? ARROW_BIG
              : d.displacement > 0.3 ? ARROW_MID
              : ARROW_SMALL,
      });
    });
    viewer.addUnitCell(afterModel, { box: { color: "#59636e" } });
    viewer.render();
  }

  function clearShapes() {
    viewer.removeAllShapes();
    viewer.addUnitCell(afterModel, { box: { color: "#59636e" } });
    viewer.render();
  }

  // ---- wire up controls ----
  // Allow #before / #after / #overlay / #diff URL hash to set the initial mode,
  // handy for screenshots and shareable links.
  const allowedModes = ["before", "after", "overlay", "diff"];
  const initialMode = allowedModes.includes(window.location.hash.replace("#", ""))
    ? window.location.hash.replace("#", "")
    : "overlay";

  const state = { mode: initialMode, arrows: true };

  document.querySelectorAll("[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-mode]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = btn.dataset.mode;
      applyStyle(state.mode);
    });
  });

  const arrowsBtn = document.getElementById("toggle-arrows");
  if (arrowsBtn) {
    arrowsBtn.addEventListener("click", () => {
      state.arrows = !state.arrows;
      arrowsBtn.classList.toggle("active", state.arrows);
      if (state.arrows) addArrows();
      else clearShapes();
    });
  }

  // initial render — apply state.mode (may be set by hash) and reflect on button
  applyStyle(state.mode);
  document.querySelectorAll("[data-mode]").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === state.mode);
  });
  addArrows();
  viewer.zoomTo();
  viewer.render();
})();
