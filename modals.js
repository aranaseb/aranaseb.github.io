//
// modals.js
// @author Sebastian Arana
//

/*  */
function openModal(selector) {
	const modal = d3.select(selector);
	modal.node().style.display = "";
	modal.classed("show", true);
}

/*  */
function closeModal(selector) {
	const modal = d3.select(selector);
	modal.classed("show", false);
	modal.node().style.display = "none";
}

/*  */
function getStationTypeDesc(pokelid, locale) {
	const type = pokelid.station_type;
	if (type === "walkable") {
		const distStr = pokelid.nearest_station_distance_km.toFixed(2) + "km";
		const nearCity = pokelid.nearest_city_distance_km < 5;
		if (nearCity) {
			const cityName = t("cities", pokelid.nearest_city, locale) || pokelid.nearest_city;
			return locale === "ja"
				? `${cityName}の中心部、最寄り駅から${distStr}`
				: `Inside ${cityName}, ${distStr} from the nearest train station`;
		} else {
			return locale === "ja"
				? `最寄り駅から${distStr}`
				: `${distStr} from the nearest train station`;
		}
	}
	return t("ui", `station_desc_${type}`, locale);
}

/*  */
function showPokelidModal(pokelid) {
	const modal = d3.select("#pokelid-modal");
	const slug = pokelid.prefecture;
	const prefNameEn = t("prefectures", slug, "en");
	const prefNameLocale = t("prefectures", slug, state.locale);

	modal.select(".modal-title").text(pokelid.name_ja && state.locale === "ja" ? pokelid.name_ja : pokelid.name);
	modal.select(".modal-prefecture").text(prefNameLocale);
	modal.select(".modal-prefecture-label").node().firstChild.textContent =
		t("ui", "prefecture_label", state.locale) + " ";
	modal.select(".modal-station-type")
		.attr("data-type", pokelid.station_type)
		.text(t("ui", `station_type_${pokelid.station_type}`, state.locale));
	modal.select(".modal-station-desc")
		.text(getStationTypeDesc(pokelid, state.locale));
	modal.select(".modal-pokelid-image")
		.attr("src", pokelid.image_local)
		.attr("alt", pokelid.name);
	modal.select(".modal-image")
		.attr("src", `backgrounds/Location_Background_Pokelid_${prefNameEn}.png`)
		.attr("alt", `${prefNameLocale} Pokélid`);
	modal.select(".modal-maps-link")
		.text(t("ui", "view_on_maps", state.locale))
		.attr("href", `https://www.google.com/maps?q=${pokelid.lat},${pokelid.lng}`);
	modal.select(".modal-pokemon-link")
		.text(t("ui", "pokemon_page", state.locale))
		.attr("href", `https://local.pokemon.jp/en/manhole/${prefNameEn.toLowerCase()}.html`);

	// Visit status
	const STATUSES = ["unvisited", "visited", "want"];
	const statusBar = modal.select(".modal-visit-status").html("");
	STATUSES.forEach(s => {
		statusBar.append("button")
			.attr("class", `visit-btn visit-btn--${s}`)
			.attr("data-status", s)
			.text(t("ui", `visit_${s}`, state.locale))
			.on("click touchend", function(event) {
				event.stopPropagation();
				setVisitStatus(pokelid.id, s);
				updateVisitButtons(modal, pokelid.id);
				clearPokelids();
				showPokelids();
			});
	});
	updateVisitButtons(modal, pokelid.id);

	openModal("#pokelid-modal");
}

/*  */
function updateVisitButtons(modal, id) {
	const status = getVisitStatus(id);
	modal.selectAll(".visit-btn").classed("visit-btn--active", false);
	modal.select(`.visit-btn[data-status="${status}"]`).classed("visit-btn--active", true);
	modal.select(".modal-visit-tag")
		.attr("data-status", status)
		.text(t("ui", `visit_${status}`, state.locale));
}

/*  */
function closePokelidModal() {
	closeModal("#pokelid-modal");
}

/*  */
function showClusterModal(cluster) {
	const modal = d3.select("#cluster-modal");
	const prefNameLocale = t("prefectures", cluster.prefecture, state.locale);
	const count = cluster.lids.length;

	modal.select(".cluster-modal-title")
		.text(`${count} ${t("ui", "pokelid_count", state.locale)} — ${prefNameLocale}`);
	modal.select(".cluster-modal-subtitle")
		.text(t("ui", "click_to_view", state.locale));

	const list = modal.select(".cluster-list").html("");
	cluster.lids.forEach(lid => {
		const item = list.append("div")
			.attr("class", "cluster-item")
			.style("cursor", "pointer")
			.on("click", () => { closeClusterModal(); showPokelidModal(lid); });
		item.append("img")
			.attr("class", "cluster-item-image")
			.attr("src", lid.image_local)
			.attr("alt", lid.name);
		const text = item.append("div").attr("class", "cluster-item-text");
		text.append("div").attr("class", "cluster-item-name").text(lid.name_ja && state.locale === "ja" ? lid.name_ja : lid.name);
		text.append("div").attr("class", "cluster-item-coords").text(lid.dms);
	});

	openModal("#cluster-modal");
}

/*  */
function closeClusterModal() {
	closeModal("#cluster-modal");
}
