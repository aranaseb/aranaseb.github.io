//
// render.js
// @author Sebastian Arana
//


const map = L.map('osm-map', { zoomControl: false }).setView([38.0, 140.8], 6);

const esriSatellite = L.tileLayer(
	'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
	{ attribution: '&copy; Esri', maxZoom: 19 }
);
const esriLabelsEn = L.tileLayer(
	'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
	{ attribution: '', maxZoom: 19 }
);
const osmJaLabels = L.tileLayer(
	'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
	{ attribution: '&copy; OpenStreetMap contributors', maxZoom: 19, opacity: 0.7 }
);

function applyTileLayer(locale) {
	if (!map.hasLayer(esriSatellite)) map.addLayer(esriSatellite);
	if (locale === 'en') {
		map.removeLayer(osmJaLabels);
		if (!map.hasLayer(esriLabelsEn)) map.addLayer(esriLabelsEn);
	} else {
		map.removeLayer(esriLabelsEn);
		if (!map.hasLayer(osmJaLabels)) map.addLayer(osmJaLabels);
	}
}

applyTileLayer(state.locale);

/*  */
const svg = d3.select(map.getPanes().overlayPane)
	.append("svg")
	.attr("class", "d3-overlay")
	.style("position", "absolute")
	.style("top", "0")
	.style("left", "0")
	.style("pointer-events", "none");
const g = svg.append("g").attr("class", "leaflet-zoom-hide");
const tooltip = d3.select("#tooltip");
const counter = d3.select("#pokelid-counter");

const pokelidLayer = g.append("g").attr("class", "pokelids").style("pointer-events", "auto");


/*  */
function redraw() {
	const size = map.getSize();
	svg
		.attr("width",  size.x)
		.attr("height", size.y);

	g.attr("transform", "translate(0,0)");

	pokelidLayer.selectAll("g.pokelid-cluster").attr("transform", d => {
		const pt = map.latLngToLayerPoint(L.latLng(d.lat, d.lng));
		return `translate(${pt.x},${pt.y})`;
	});
}

/*  */
function setLocale(locale) {
	state.locale = locale;
	localStorage.setItem("pokelid-locale", locale);
	document.documentElement.lang = locale;
	applyTileLayer(locale);
	d3.select("#lang-toggle").text(t("ui", "lang_toggle", locale));
	if (typeof updateFilterLabels === "function") updateFilterLabels(locale);
	if (typeof updatePrefectureLabels === "function") updatePrefectureLabels(locale);
	if (typeof updatePrefsLabels === "function") updatePrefsLabels(locale);
	if (typeof updateExportLabel === "function") updateExportLabel(locale);
	updateCounter();
	showPokelids();
}

// ─── Counter ──────────────────────────────────────────────────────────────────

/*  */
function getFilteredPokelids() {
	if (state.activeFilters.size === 0 && state.activeVisitFilters.size === 0) return state.pokelids;
	const filtered = {};
	for (const [pref, lids] of Object.entries(state.pokelids)) {
		const kept = lids.filter(l => {
			if (state.activeFilters.size > 0 && !state.activeFilters.has(l.station_type)) return false;
			if (state.activeVisitFilters.size > 0 && !state.activeVisitFilters.has(getVisitStatus(l.id))) return false;
			return true;
		});
		if (kept.length) filtered[pref] = kept;
	}
	return filtered;
}

/*  */
function updateCounter() {
	const sel = state.selectedPrefectures;
	const source = getFilteredPokelids();
	const count = sel.size === 0
		? Object.values(source).reduce((s, a) => s + a.length, 0)
		: Array.from(sel).reduce((s, slug) => s + (source[slug]?.length ?? 0), 0);
	counter.text(`${count} ${t("ui", "pokelids_total", state.locale)}`);
}

// ─── Pokelid clusters ─────────────────────────────────────────────────────────

/*  */
function renderClusterCircle(enter) {
	const scale = getMarkerScale();

	enter.filter(d => d.lids.length > 1).each(function(d) {
		const allVisited = d.lids.every(l => getVisitStatus(l.id) === "visited");
		d3.select(this).append("circle")
			.attr("class", "pokelid-circle")
			.attr("r", baseClusterRadius * scale)
			.attr("fill", "#ff6b6b")
			.attr("stroke", "white")
			.attr("stroke-width", 0.25 * screenScale)
			.attr("opacity", allVisited ? 0.35 : 0.9);
	});

	enter.filter(d => d.lids.length === 1).each(function(d) {
		const grp = d3.select(this);
		const lid = d.lids[0];
		const r = imageRadius * scale;
		const clipId = "clip-" + lid.image_local.replace(/[^a-z0-9]/gi, "-");
		const status = getVisitStatus(lid.id);
		grp.append("circle")
			.attr("r", r + 1)
			.attr("fill", "white")
			.attr("opacity", 0.7);
		grp.append("clipPath")
			.attr("id", clipId)
			.append("circle")
			.attr("r", r);
		grp.append("image")
			.attr("class", "pokelid-image")
			.attr("href", lid.image_local)
			.attr("x", -r)
			.attr("y", -r)
			.attr("width", r * 2)
			.attr("height", r * 2)
			.attr("clip-path", `url(#${clipId})`)
			.attr("opacity", status === "visited" ? 0.35 : 1);
	});
}

/*  */
function renderClusterCount(enter) {
	const scale = getMarkerScale();
	enter.filter(d => d.lids.length > 1)
		.append("text")
		.attr("class", "cluster-count")
		.attr("text-anchor", "middle")
		.attr("dy", "0.35em")
		.attr("font-size", `${baseCountSize * scale}px`)
		.attr("font-weight", "bold")
		.attr("fill", "white")
		.attr("stroke", "black")
		.attr("stroke-width", 0.2 * screenScale)
		.attr("paint-order", "stroke")
		.text(d => d.lids.length);
}

/*  */
function clusterTooltipText(d) {
	return d.lids.length > 1
		? `${d.lids.length} ${t("ui", "pokelids_in_area", state.locale)}`
		: `${(d.lids[0].name_ja && state.locale === "ja" ? d.lids[0].name_ja : d.lids[0].name)}<br>${d.lids[0].dms}`;
}

/*  */
function onClusterClick(event, d) {
	event.stopPropagation();
	event.preventDefault();
	if (event.type === "touchend") {
		const touch = event.changedTouches[0];
		const elem = document.elementFromPoint(touch.clientX, touch.clientY);
		if (!this.contains(elem) && elem !== this) return;
	}
	d.lids.length === 1 ? showPokelidModal(d.lids[0]) : showClusterModal(d);
}

/*  */
function showPokelids() {
	const clusters = clusterPokelids(getVisiblePoints());
	pokelidLayer.selectAll("g.pokelid-cluster").remove();
	const groups = pokelidLayer.selectAll("g.pokelid-cluster")
		.data(clusters, d => `${d.prefecture}-${d.lat},${d.lng}-${d.lids.length}`)
		.enter()
		.append("g")
		.attr("class", "pokelid-cluster")
		.style("cursor", "pointer");

	renderClusterCircle(groups);
	renderClusterCount(groups);

	groups
		.attr("transform", d => {
			const pt = map.latLngToLayerPoint(L.latLng(d.lat, d.lng));
			return `translate(${pt.x},${pt.y})`;
		})
		.on("mousemove touchmove", function(event, d) {
			const e = event.type === "touchmove" ? event.touches[0] : event;
			tooltip.style("opacity", 1)
				.html(clusterTooltipText(d))
				.style("left", (e.pageX + 12) + "px")
				.style("top", (e.pageY + 12) + "px");
		})
		.on("mouseout touchend", () => tooltip.style("opacity", 0))
		.on("click touchend", onClusterClick);
}

/*  */
function clearPokelids() {
	pokelidLayer.selectAll("g.pokelid-cluster").remove();
}
