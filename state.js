//
// state.js
// @author Sebastian Arana
//

/*  */
const CLUSTER_DISTANCE_KM = 5;
const MAINLAND_BOUNDS = { lat: [30, 46], lng: [128, 146] };

/*  */
const ZOOM_FAR   = 8;
const ZOOM_CLOSE = 11;

/*  */
function getZoomTier() {
	const z = map.getZoom();
	if (z < ZOOM_FAR)   return "far";
	if (z >= ZOOM_CLOSE) return "close";
	return "mid";
}

/*  */
const screenScale = 1;
const imageRadius = 12;
const baseClusterRadius = 12;
const baseCountSize = 14;

/*  */
function getMarkerScale() {
	return getZoomTier() === "far" ? 0.55 : 1;
}

/*  */
const state = {
	pokelids: {},
	translations: {},
	selectedPrefectures: new Set(),
	activeFilters: new Set(),
	activeVisitFilters: new Set(),
	pokelidsReady: false,
	zoomReady: false,
	locale: localStorage.getItem("pokelid-locale") ?? "en",
};

/*  */
const visits = JSON.parse(localStorage.getItem("pokelid-visits") ?? "{}");

/*  */
function getVisitStatus(id) {
	return visits[id] ?? "unvisited";
}

/*  */
function setVisitStatus(id, status) {
	if (status === "unvisited") {
		delete visits[id];
	} else {
		visits[id] = status;
	}
	localStorage.setItem("pokelid-visits", JSON.stringify(visits));
	if (typeof updateExportButton === "function") updateExportButton();
}


/*  */
function t(type, key, locale = "en") {
	return state.translations[type]?.[key]?.[locale] ?? key;
}

/*  */
function prefSlug(feature) {
	return feature.properties.slug;
}

/*  */
Promise.all([
	d3.json("data/translations.json"),
	d3.json("data/pokelids.json"),
]).then(([translations, pokelids]) => {
	state.translations = translations;
	state.pokelids = pokelids;
	state.pokelidsReady = true;
	if (typeof onBothReady === "function") onBothReady();
});
