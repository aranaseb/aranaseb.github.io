//
// export.js
// @author Sebastian Arana
//

/*  */
function getWantPokelids() {
	const results = [];
	for (const [slug, lids] of Object.entries(state.pokelids)) {
		lids.forEach(l => {
			if (getVisitStatus(l.id) === "want") results.push({ ...l, prefecture: slug });
		});
	}
	return results;
}

/*  */
function buildKML(pokelids) {
	const placemarks = pokelids.map(l => {
		const name = (l.name_ja && state.locale === "ja") ? l.name_ja : l.name;
		const pref = t("prefectures", l.prefecture, state.locale);
		return `    <Placemark>
      <name>${escapeXml(name)}</name>
      <description>${escapeXml(pref)}</description>
      <Point>
        <coordinates>${l.lng},${l.lat},0</coordinates>
      </Point>
    </Placemark>`;
	}).join("\n");

	return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Pokélid Plan to Visit</name>
${placemarks}
  </Document>
</kml>`;
}

/*  */
function escapeXml(str) {
	return str
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;");
}

/*  */
function downloadKML() {
	const pokelids = getWantPokelids();
	if (pokelids.length === 0) return;
	const kml = buildKML(pokelids);
	const blob = new Blob([kml], { type: "application/vnd.google-earth.kml+xml" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = "pokelid-plan-to-visit.kml";
	a.click();
	URL.revokeObjectURL(url);
}

/*  */
function updateExportButton() {
	const btn = document.getElementById("export-kml-btn");
	if (!btn) return;
	// Check localStorage directly so this works before state.pokelids loads
	const visits = JSON.parse(localStorage.getItem("pokelid-visits") ?? "{}");
	const hasWant = Object.values(visits).some(v => v === "want");
	btn.style.display = hasWant ? "" : "none";
	if (hasWant) btn.textContent = typeof t === "function" ? t("ui", "export_kml", state.locale) : "📍 Export Plan to Visit";
}

/*  */
function initExport() {
	const btn = document.getElementById("export-kml-btn");
	if (btn) btn.addEventListener("click", downloadKML);
}

function updateExportLabel(locale) {
	const btn = document.getElementById("export-kml-btn");
	if (btn && btn.style.display !== "none") btn.textContent = t("ui", "export_kml", locale);
}

initExport();
updateExportButton();
