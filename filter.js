//
// filter.js
// @author Sebastian Arana
//

const FILTER_TYPES = ["major", "local", "walkable", "roadside", "remote", "super_remote"];

/*  */
function applyFilters() {
	state.activeFilters = new Set(
		FILTER_TYPES.filter(tp => {
			const cb = document.getElementById("filter-" + tp);
			return cb && cb.checked;
		})
	);
	clearPokelids();
	showPokelids();
	updateCounter();
}

const VISIT_STATUSES = ["unvisited", "visited", "want"];

/*  */
function applyVisitFilters() {
	state.activeVisitFilters = new Set(
		VISIT_STATUSES.filter(s => {
			const cb = document.getElementById("filter-visit-" + s);
			return cb && cb.checked;
		})
	);
	clearPokelids();
	showPokelids();
	updateCounter();
}

/*  */
function updateFilterLabels(locale) {
	document.getElementById("filter-title").textContent = t("ui", "filter_title", locale);
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

/*  */
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

	// "All types" — clear station type filters
	allCb.addEventListener("change", () => {
		if (allCb.checked) {
			FILTER_TYPES.forEach(tp => {
				const cb = document.getElementById("filter-" + tp);
				if (cb) cb.checked = false;
			});
			state.activeFilters = new Set();
			clearPokelids();
			showPokelids();
			updateCounter();
		}
	});

	// Individual station type checkboxes
	FILTER_TYPES.forEach(type => {
		const cb = document.getElementById("filter-" + type);
		if (!cb) return;
		cb.addEventListener("change", () => {
			if (allCb) allCb.checked = false;
			applyFilters();
		});
	});

	// "All" visit status — clear visit filters
	visitAllCb.addEventListener("change", () => {
		if (visitAllCb.checked) {
			VISIT_STATUSES.forEach(s => {
				const cb = document.getElementById("filter-visit-" + s);
				if (cb) cb.checked = false;
			});
			state.activeVisitFilters = new Set();
			clearPokelids();
			showPokelids();
			updateCounter();
		}
	});

	// Individual visit status checkboxes
	VISIT_STATUSES.forEach(s => {
		const cb = document.getElementById("filter-visit-" + s);
		if (!cb) return;
		cb.addEventListener("change", () => {
			if (visitAllCb) visitAllCb.checked = false;
			applyVisitFilters();
		});
	});
}
