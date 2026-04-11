//
// map.js
// @author Sebastian Arana
//

/*  */
function onBothReady() {
	if (!state.pokelidsReady || !state.zoomReady) return;
	if (typeof updateFilterLabels === "function") updateFilterLabels(state.locale);
	if (typeof updatePrefectureLabels === "function") updatePrefectureLabels(state.locale);
	if (typeof updatePrefsLabels === "function") updatePrefsLabels(state.locale);
	if (typeof updateExportButton === "function") updateExportButton();
	if (typeof updateExportLabel === "function") updateExportLabel(state.locale);
	showPokelids();
	updateCounter();
}

/*  */
function initInitialZoom() {
	state.zoomReady = true;
	map.on("moveend", redraw);
	map.on("zoomend", () => {
		clearPokelids();
		showPokelids();
		updateCounter();
		redraw();
	});
	map.whenReady(() => {
		redraw();
		onBothReady();
	});
}

initInitialZoom();

// ─── Global event handlers ────────────────────────────────────────────────────

/*  */
d3.select("#pokelid-modal").on("click", function(event) {
	if (event.target === this) closePokelidModal();
});
d3.select(".modal-close").on("click", function(event) {
	event.stopPropagation();
	closePokelidModal();
});

/*  */
d3.select("#cluster-modal").on("click", function(event) {
	if (event.target === this) closeClusterModal();
});
d3.select(".cluster-modal-close").on("click", function(event) {
	event.stopPropagation();
	closeClusterModal();
});

/*  */
d3.select("#lang-toggle").on("click", function() {
	setLocale(state.locale === "en" ? "ja" : "en");
});

/*  */
initPrefecturePanel();
initFilter();
