//
// render.js
// @author Sebastian Arana
//

/*  */
const regionColors = d3.scaleOrdinal()
	.domain([
		"hokkaido-tohoku",
		"kanto",
		"chubu",
		"kinki",
		"chugoku-shikoku",
		"kyushu-okinawa"
	])
	.range(["#048c28"]);

/*  */
const projection = d3.geoEquirectangular();
const path = d3.geoPath().projection(projection);
const tooltip = d3.select("#tooltip");
const counter = d3.select("#pokelid-counter");

/*  */
const svg = d3.select("svg").attr("width", WIDTH).attr("height", HEIGHT);
const g = svg.append("g").attr("width", WIDTH).attr("height", HEIGHT);
const satelliteLayer = g.append("g").attr("class", "satellite");
const prefLayer = g.append("g").attr("class", "prefectures");
const pokelidLayer = g.append("g").attr("class", "pokelids");
const cityLayer = g.append("g").attr("class", "cities");

/*  */
const zoom = d3.zoom().scaleExtent([1, 20])
	.on("zoom", event => g.attr("transform", event.transform));
svg.call(zoom);

/*  */
function initZoomExtent() {
	const [x0, y1] = projection([122, 24]);
	const [x1, y0] = projection([148, 46]);
	const imgW = x1 - x0;
	const imgH = y1 - y0;
	const minScale = Math.max(WIDTH / imgW, HEIGHT / imgH);
	zoom.scaleExtent([minScale, 20]);
	zoom.constrain((transform) => {
		const screenX0 = transform.applyX(x0);
		const screenX1 = transform.applyX(x1);
		const screenY0 = transform.applyY(y0);
		const screenY1 = transform.applyY(y1);
		let dx = 0, dy = 0;
		if (screenX0 > 0) dx = -screenX0;
		else if (screenX1 < WIDTH) dx = WIDTH - screenX1;
		if (screenY0 > 0) dy = -screenY0;
		else if (screenY1 < HEIGHT) dy = HEIGHT - screenY1;
		return transform.translate(dx / transform.k, dy / transform.k);
	});
}

/*  */
function setLocale(locale) {
	state.locale = locale;
	document.documentElement.lang = locale;
	d3.select("#lang-toggle").text(t("ui", "lang_toggle", locale));
	if (typeof updateFilterLabels === "function") updateFilterLabels(locale);
	cityLayer.selectAll("g.city").each(function(d) {
		d3.select(this).select(".city-label").text(t("cities", d.key, locale) || d.city);
	});
	updateCounter();
	showPokelids();
}

// ─── Satellite layer ──────────────────────────────────────────────────────────

/*  */
function initSatellite() {
	const [x0, y1] = projection([122, 24]);
	const [x1, y0] = projection([148, 46]);
	satelliteLayer.append("image")
		.attr("class", "satellite-image")
		.attr("href", "data/japan_satellite.jpg")
		.attr("x", x0)
		.attr("y", y0)
		.attr("width", x1 - x0)
		.attr("height", y1 - y0)
		.attr("preserveAspectRatio", "none");
}

// ─── Counter ──────────────────────────────────────────────────────────────────

/*  */
function getFilteredPokelids() {
	if (state.activeFilters.size === 0) return state.pokelids;
	const filtered = {};
	for (const [pref, lids] of Object.entries(state.pokelids)) {
		const kept = lids.filter(l => state.activeFilters.has(l.station_type));
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
	enter.filter(d => d.lids.length > 1)
		.append("circle")
		.attr("class", "pokelid-circle")
		.attr("r", baseClusterRadius)
		.attr("fill", "#ff6b6b")
		.attr("stroke", "black")
		.attr("stroke-width", 0.25 * screenScale)
		.attr("opacity", 0.9);

	enter.filter(d => d.lids.length === 1).each(function(d) {
		const grp = d3.select(this);
		const clipId = "clip-" + d.lids[0].image_local.replace(/[^a-z0-9]/gi, "-");
		grp.append("clipPath")
			.attr("id", clipId)
			.append("circle")
			.attr("r", imageRadius);
		grp.append("image")
			.attr("class", "pokelid-image")
			.attr("href", d.lids[0].image_local)
			.attr("x", -imageRadius)
			.attr("y", -imageRadius)
			.attr("width", imageRadius * 2)
			.attr("height", imageRadius * 2)
			.attr("clip-path", `url(#${clipId})`);
	});
}

/*  */
function renderClusterCount(enter) {
	enter.filter(d => d.lids.length > 1)
		.append("text")
		.attr("class", "cluster-count")
		.attr("text-anchor", "middle")
		.attr("dy", "0.35em")
		.attr("font-size", `${baseCountSize}px`)
		.attr("font-weight", "bold")
		.attr("fill", "white")
		.attr("stroke", "black")
		.attr("stroke-width", 0.15 * screenScale)
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
	if (!prefs.pokelids) return;
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
			const [x, y] = projection([d.lng, d.lat]);
			return `translate(${x},${y})`;
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

// ─── Cities ───────────────────────────────────────────────────────────────────

/*  */
function initCities(cities) {
	cityLayer.selectAll("g.city")
		.data(cities)
		.join("g")
		.attr("class", "city")
		.style("display", "block")
		.each(function(d) {
			const group = d3.select(this);
			group.append("circle")
				.attr("r", baseCityRadius)
				.attr("fill", "#000")
				.attr("stroke", "#fff")
				.attr("stroke-width", 0.25 * screenScale);
			group.append("text")
				.attr("class", "city-label")
				.text(t("cities", d.key, state.locale) || d.city)
				.attr("x", 1).attr("y", 1)
				.attr("font-size", `${baseFontSize}px`)
				.attr("font-family", "sans-serif")
				.attr("fill", "#333")
				.attr("paint-order", "stroke")
				.attr("stroke", "white")
				.attr("stroke-width", 0.5 * screenScale)
				.style("pointer-events", "none");
		})
		.attr("transform", d => {
			const [x, y] = projection([+d.lng, +d.lat]);
			return `translate(${x},${y})`;
		});
}

/*  */
function filterCitiesByPrefecture() {
	if (!prefs.cities) return;
	if (state.selectedPrefectures.size === 0) {
		cityLayer.selectAll("g.city").style("display", "block");
		return;
	}
	const prefFeatures = prefLayer.selectAll(".prefecture").data();
	cityLayer.selectAll("g.city").style("display", function(d) {
		for (const slug of state.selectedPrefectures) {
			const feat = prefFeatures.find(f => f.properties.slug === slug);
			if (feat && d3.geoContains(feat, [d.lng, d.lat])) return "block";
		}
		return "none";
	});
}

// ─── Prefectures ──────────────────────────────────────────────────────────────

/*  */
function prefTooltipText(slug, count) {
	const name = t("prefectures", slug, state.locale);
	return `${name}<br>${count} ${t("ui", "pokelid_count", state.locale)}`;
}

/*  */
function getPokelidCount(slug) {
	return (state.pokelids[slug] ?? []).length;
}

/*  */
function prefFill() {
	return prefs.satellite ? "transparent" : "#6a9e5a";
}

/*  */
function resetColors() {
	prefLayer.selectAll(".prefecture")
		.classed("selected", false);
	state.selectedPrefectures.clear();
}

/*  */
function initPrefectures(features) {
	prefLayer.selectAll(".prefecture")
		.data(features)
		.join("path")
		.attr("class", "prefecture")
		.attr("d", path)
		.attr("stroke", "#ffffff")
		.attr("stroke-width", 0.5)
		.attr("stroke-opacity", 0.7)
		.style("cursor", "pointer")
		.on("mousemove touchmove", function(event, d) {
			const e = event.type === "touchmove" ? event.touches[0] : event;
			const slug = prefSlug(d);
			tooltip.style("opacity", 1)
				.html(prefTooltipText(slug, getPokelidCount(slug)))
				.style("left", (e.pageX + 12) + "px")
				.style("top", (e.pageY + 12) + "px");
		})
		.on("mouseout touchend", () => tooltip.style("opacity", 0))
		.on("click touchend", onPrefectureClick);
}

// ─── Zoom ─────────────────────────────────────────────────────────────────────

/*  */
function getBoundsForFeature(feature) {
	const slug = feature.properties.slug;
	if (customZoomBounds[slug]) {
		const c = customZoomBounds[slug];
		const [x0, y0] = projection([c.lng[0], c.lat[1]]);
		const [x1, y1] = projection([c.lng[1], c.lat[0]]);
		return { minX: x0, minY: y0, maxX: x1, maxY: y1 };
	}
	const [[x0, y0], [x1, y1]] = path.bounds(feature);
	return { minX: x0, minY: y0, maxX: x1, maxY: y1 };
}

/*  */
function zoomToTransform(transform, duration = 750) {
	svg.transition().duration(duration).call(zoom.transform, transform);
}

/*  */
function zoomToSelection() {
	if (state.selectedPrefectures.size === 0) {
		zoomToTransform(state.initialTransform);
		return;
	}
	const features = prefLayer.selectAll(".prefecture").data()
		.filter(f => state.selectedPrefectures.has(f.properties.slug));
	if (!features.length) return;

	let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	features.forEach(f => {
		const b = getBoundsForFeature(f);
		minX = Math.min(minX, b.minX); minY = Math.min(minY, b.minY);
		maxX = Math.max(maxX, b.maxX); maxY = Math.max(maxY, b.maxY);
	});

	const scale = Math.min(10, 0.8 / Math.max((maxX - minX) / WIDTH, (maxY - minY) / HEIGHT));
	const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
	zoomToTransform(d3.zoomIdentity.translate(WIDTH / 2, HEIGHT / 2).scale(scale).translate(-cx, -cy));
}
