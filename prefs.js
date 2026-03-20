//
// prefs.js
// @author Sebastian Arana
//

/*  */
const prefs = {
	cities: true,
	pokelids: true,
	borders: true,
	satellite: false,
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
		case "satellite":
			satelliteLayer.style("display", prefs.satellite ? "" : "none");
			prefLayer.classed("satellite-off", !prefs.satellite);
			break;
	}
}


/*  */
function initPrefs() {
	const panel = document.getElementById("prefs-panel");

	document.getElementById("prefs-toggle").addEventListener("click", () => {
		panel.classList.toggle("open");
	});
	document.getElementById("prefs-close").addEventListener("click", () => {
		panel.classList.remove("open");
	});

	["cities", "pokelids", "borders", "satellite"].forEach(key => {
		const checkbox = document.getElementById(`pref-${key}`);
		checkbox.checked = prefs[key];
		checkbox.addEventListener("change", () => {
			prefs[key] = checkbox.checked;
			applyPref(key);
		});
	});

	// Apply non-default prefs on init
	applyPref("satellite");
}

