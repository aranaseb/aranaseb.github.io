//
// filter.js
// @author Sebastian Arana
//

const FILTER_TYPES   = ["major", "local", "walkable", "roadside", "remote", "super_remote"];
const VISIT_STATUSES = ["unvisited", "visited", "want"];

/* Refresh the map display and counter after any filter change. */
function refreshDisplay() {
	clearPokelids();
	showPokelids();
	updateCounter();
}

/* Build an active-filter Set from a list of checkbox ids and write it to state. */
function applyCheckboxFilters(values, idPrefix, stateKey) {
	state[stateKey] = new Set(
		values.filter(v => {
			const cb = document.getElementById(idPrefix + v);
			return cb && cb.checked;
		})
	);
	refreshDisplay();
}

function applyFilters() {
	applyCheckboxFilters(FILTER_TYPES, "filter-", "activeFilters");
}

function applyVisitFilters() {
	applyCheckboxFilters(VISIT_STATUSES, "filter-visit-", "activeVisitFilters");
}

/* Update all translatable labels in the filter panel. */
function updateFilterLabels(locale) {
	document.getElementById("filter-title").textContent  = t("ui", "filter_title", locale);
	document.getElementById("filter-toggle").textContent = "⚡ " + t("ui", "filter_title", locale);

	const visitsTitle = document.getElementById("filter-visits-title");
	if (visitsTitle) visitsTitle.textContent = t("ui", "filter_visits_title", locale);

	const allLabel = document.querySelector("label[for='filter-all'] .filter-label-text");
	if (allLabel) allLabel.textContent = t("ui", "filter_all", locale);

	FILTER_TYPES.forEach(tp => {
		const label = document.querySelector(`label[for='filter-${tp}'] .filter-label-text`);
		if (label) label.textContent = t("ui", "station_type_" + tp, locale);
	});

	const visitAllLabel = document.querySelector("label[for='filter-visit-all'] .visit-filter-label-text");
	if (visitAllLabel) visitAllLabel.textContent = t("ui", "filter_visit_all", locale);

	VISIT_STATUSES.forEach(s => {
		const label = document.querySelector(`label[for='filter-visit-${s}'] .visit-filter-label-text`);
		if (label) label.textContent = t("ui", `visit_${s}`, locale);
	});
}

/*
 * Wire up a "select all" checkbox alongside its individual item checkboxes.
 *   allCb     – the "All …" checkbox element
 *   values    – array of value strings (FILTER_TYPES or VISIT_STATUSES)
 *   idPrefix  – id prefix for individual checkboxes  ("filter-" / "filter-visit-")
 *   stateKey  – key on `state` to clear when "All" is selected
 *   applyFn   – function to call when an individual checkbox changes
 */
function initFilterGroup(allCb, values, idPrefix, stateKey, applyFn) {
	allCb.addEventListener("change", () => {
		if (!allCb.checked) return;
		values.forEach(v => {
			const cb = document.getElementById(idPrefix + v);
			if (cb) cb.checked = false;
		});
		state[stateKey] = new Set();
		refreshDisplay();
	});

	values.forEach(v => {
		const cb = document.getElementById(idPrefix + v);
		if (!cb) return;
		cb.addEventListener("change", () => {
			allCb.checked = false;
			applyFn();
		});
	});
}

function initFilter() {
	const filterPanel = document.getElementById("filter-panel");
	const filterClose = document.getElementById("filter-close");
	const allCb       = document.getElementById("filter-all");
	const visitAllCb  = document.getElementById("filter-visit-all");

	document.getElementById("filter-toggle").addEventListener("click", () => {
		filterPanel.classList.toggle("open");
	});

	filterClose.addEventListener("click", () => {
		filterPanel.classList.remove("open");
	});

	initFilterGroup(allCb,      FILTER_TYPES,   "filter-",       "activeFilters",      applyFilters);
	initFilterGroup(visitAllCb, VISIT_STATUSES, "filter-visit-", "activeVisitFilters", applyVisitFilters);
}
