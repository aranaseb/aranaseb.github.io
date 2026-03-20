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
	updateCounter();
}

/*  */
function initInitialZoom() {
	const [x0, y1] = projection([122, 24]);
	const [x1, y0] = projection([148, 46]);
	const imgW = x1 - x0;
	const imgH = y1 - y0;
	const scale = Math.max(WIDTH / imgW, HEIGHT / imgH);
	const cx = (x0 + x1) / 2;
	const transform = d3.zoomIdentity
		.translate(WIDTH / 2, 0)
		.scale(scale)
		.translate(-cx, -y0);
	svg.call(zoom.transform, transform);
	state.initialTransform = transform;
	state.zoomReady = true;
	initZoomExtent();
	onBothReady();
}

/*  */
d3.json("data/jp.json").then(function(geojson) {
	projection.fitExtent([[PADDING, PADDING], [WIDTH - PADDING, HEIGHT - PADDING]], geojson);
	initSatellite(geojson);
	initPrefectures(geojson.features);
	pokelidLayer.raise();
	cityLayer.raise();
	initInitialZoom();
	if (state.cities.length) {
		initCities(state.cities);
	} else {
		// translations/cities may not be ready yet — wait for them
		const interval = setInterval(() => {
			if (state.cities.length) {
				clearInterval(interval);
				initCities(state.cities);
			}
		}, 50);
	}
});

// ─── Global event handlers ────────────────────────────────────────────────────

/*  */
svg.on("click", (event) => {
	if (event.target !== svg.node()) return;
	resetColors();
	clearPokelids();
	showPokelids();
	filterCitiesByPrefecture();
	updateCounter();
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

/*  */
initPrefs();
