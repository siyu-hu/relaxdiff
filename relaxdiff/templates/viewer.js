// In-page viewer logic. Reads window.__RELAXDIFF__ payload and drives 3Dmol.js.

(function () {
  const data = window.__RELAXDIFF__;
  if (!data) return;

  const containerId = "viewer";
  const viewer = $3Dmol.createViewer(containerId, { backgroundColor: "#050709" });

  function addStructure(cif, opacity, hidden) {
    const model = viewer.addModel(cif, "cif", { keepH: true });
    model.setStyle({}, { stick: { radius: 0.12 }, sphere: { scale: 0.28, opacity: opacity } });
    if (hidden) viewer.setStyle({ model: model }, { sphere: { hidden: true }, stick: { hidden: true } });
    return model;
  }

  const beforeModel = addStructure(data.before_cif, 0.5, false);
  const afterModel = addStructure(data.after_cif, 1.0, false);

  function addArrows() {
    const top = [...data.displacements]
      .sort((a, b) => b.displacement - a.displacement)
      .slice(0, Math.min(20, data.displacements.length));

    // Pull start positions from the after model atoms in input order
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
        radius: 0.06,
        radiusRatio: 2.0,
        color: d.displacement > 1.0 ? "#f85149" : d.displacement > 0.3 ? "#d29922" : "#58a6ff",
      });
    });
  }

  function addUnitCell() {
    viewer.addUnitCell(afterModel, { box: { color: "#3a4252" } });
  }

  addArrows();
  addUnitCell();
  viewer.zoomTo();
  viewer.render();

  // Toggle modes
  const state = { mode: "both", arrows: true };

  function setMode(mode) {
    state.mode = mode;
    if (mode === "before") {
      viewer.setStyle({ model: beforeModel }, { stick: { radius: 0.14 }, sphere: { scale: 0.32 } });
      viewer.setStyle({ model: afterModel }, { stick: { hidden: true }, sphere: { hidden: true } });
    } else if (mode === "after") {
      viewer.setStyle({ model: beforeModel }, { stick: { hidden: true }, sphere: { hidden: true } });
      viewer.setStyle({ model: afterModel }, { stick: { radius: 0.14 }, sphere: { scale: 0.32 } });
    } else {
      viewer.setStyle({ model: beforeModel }, { stick: { radius: 0.10 }, sphere: { scale: 0.24, opacity: 0.45 } });
      viewer.setStyle({ model: afterModel }, { stick: { radius: 0.14 }, sphere: { scale: 0.30 } });
    }
    viewer.render();
  }

  function toggleArrows() {
    state.arrows = !state.arrows;
    viewer.removeAllShapes();
    if (state.arrows) addArrows();
    addUnitCell();
    viewer.render();
  }

  document.querySelectorAll("[data-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-mode]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      setMode(btn.dataset.mode);
    });
  });

  const arrowsBtn = document.getElementById("toggle-arrows");
  if (arrowsBtn) {
    arrowsBtn.addEventListener("click", () => {
      arrowsBtn.classList.toggle("active");
      toggleArrows();
    });
  }

  // Default: both view + arrows
  setMode("both");
})();
