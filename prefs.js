//
// prefs.js
// @author Sebastian Arana
//

/*  */
const prefs = {
	cities: true,
	pokelids: true,
	borders: true,
};

/*  */
function applyPref(key) {
	switch (key) {
		case "cities":
			if (prefs.cities) {
				filterCitiesByPrefecture();
			} else {
				cityLayer.selectAll("g.city").style("display", "none");
			}
			break;
		case "pokelids":
			pokelidLayer.style("display", prefs.pokelids ? "" : "none");
			break;
		case "borders":
			prefLayer.selectAll(".prefecture")
				.style("stroke", prefs.borders ? "" : "none");
			break;
	}
}

/*  */
function updatePrefsLabels(locale) {
	document.getElementById("prefs-title").textContent  = t("ui", "layers_title",  locale);
	document.getElementById("prefs-toggle").textContent = t("ui", "layers_button", locale);
	[["pref-cities",   "layer_cities"],
	 ["pref-pokelids", "layer_pokelids"],
	 ["pref-borders",  "layer_borders"],
	].forEach(([id, key]) => {
		document.getElementById(id)
			.closest("label")
			.querySelector(".prefs-label")
			.textContent = t("ui", key, locale);
	});
}

/*  */
function initPrefs() {
	const panel       = document.getElementById("prefs-panel");
	const filterPanel = document.getElementById("filter-panel");

	document.getElementById("prefs-toggle").addEventListener("click", () => {
		panel.classList.toggle("open");
		if (filterPanel) filterPanel.classList.remove("open");
	});
	document.getElementById("prefs-close").addEventListener("click", () => {
		panel.classList.remove("open");
	});

	["cities", "pokelids", "borders"].forEach(key => {
		const checkbox = document.getElementById(`pref-${key}`);
		checkbox.checked = prefs[key];
		checkbox.addEventListener("change", () => {
			prefs[key] = checkbox.checked;
			applyPref(key);
		});
	});
}
