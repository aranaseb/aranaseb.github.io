//
// state.js
// @author Sebastian Arana
//

/*  */
const WIDTH = window.innerWidth;
const HEIGHT = window.innerHeight;
const PADDING = 50;
const CLUSTER_DISTANCE_KM = 5;
const MAINLAND_BOUNDS = { lat: [30, 46], lng: [128, 146] };

/*  */
const screenScale = Math.min(WIDTH, HEIGHT) / 1000;
const baseFontSize = 3 * screenScale;
const baseCityRadius = 0.5 * screenScale;
const imageRadius = 1.5 * screenScale;
const baseClusterRadius = 1.8 * screenScale;
const baseCountSize = 2.5 * screenScale;

/*  */
const state = {
	pokelids: {},
	translations: {},
	cities: [],
	selectedPrefectures: new Set(),
	initialTransform: null,
	pokelidsReady: false,
	zoomReady: false,
	locale: "en",
};

/*  */
const customZoomBounds = {
	"tokyo": { lat: [35.5, 35.85], lng: [139.3, 139.9] }
};

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
	d3.json("translations.json"),
	d3.json("pokelids.json"),
	d3.json("jpcities.json"),
]).then(([translations, pokelids, cities]) => {
	state.translations = translations;
	state.pokelids = pokelids;
	state.cities = cities;
	state.pokelidsReady = true;
	onBothReady();
});
