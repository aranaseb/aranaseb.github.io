//
// map.js
// @author Sebastian Arana
//

/*  */
function onBothReady() {
	if (!state.pokelidsReady || !state.zoomReady) return;
	showPokelids();
	updateCounter();
}

/*  */
function onPrefectureClick(event, d) {
	event.stopPropagation();
	event.preventDefault();
	if (event.type === "touchend") {
		const touch = event.changedTouches[0];
		if (document.elementFromPoint(touch.clientX, touch.clientY) !== this) return;
	}
	const slug = prefSlug(d);
	if (state.selectedPrefectures.has(slug)) {
		state.selectedPrefectures.delete(slug);
		d3.select(this).classed("selected", false);
	} else {
		state.selectedPrefectures.add(slug);
		d3.select(this).classed("selected", true);
	}
	clearPokelids();
	showPokelids();
	filterCitiesByPrefecture();
	zoomToSelection();
	updateCounter();
}

/*  */
function initInitialZoom() {
	const [x0, y0] = projection([MAINLAND_BOUNDS.lng[0], MAINLAND_BOUNDS.lat[1]]);
	const [x1, y1] = projection([MAINLAND_BOUNDS.lng[1], MAINLAND_BOUNDS.lat[0]]);
	const scale = Math.min(8, 0.9 / Math.max((x1 - x0) / WIDTH, (y1 - y0) / HEIGHT));
	const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
	svg.transition().duration(1000)
		.call(zoom.transform, d3.zoomIdentity.translate(WIDTH / 2, HEIGHT / 2).scale(scale).translate(-cx, -cy))
		.on("end", () => {
			state.initialTransform = d3.zoomTransform(svg.node());
			state.zoomReady = true;
			onBothReady();
		});
}

/*  */
d3.json("jp.json").then(function(geojson) {
	projection.fitExtent([[PADDING, PADDING], [WIDTH - PADDING, HEIGHT - PADDING]], geojson);
	initPrefectures(geojson.features);
	pokelidLayer.raise();
	cityLayer.raise();
	initInitialZoom();
	d3.json("jpcities.json").then(initCities);
});

// ─── Global event handlers ────────────────────────────────────────────────────

/*  */
svg.on("click", () => {
	resetColors();
	clearPokelids();
	showPokelids();
	cityLayer.selectAll("g.city").style("display", "none");
	updateCounter();
	zoomToTransform(state.initialTransform);
});

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
