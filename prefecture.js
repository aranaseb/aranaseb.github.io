//
// prefecture.js
// @author Sebastian Arana
//

const PREFECTURE_SLUGS = [
	"hokkaido",
	"aomori", "iwate", "miyagi", "akita", "yamagata", "fukushima",
	"ibaraki", "tochigi", "gunma", "saitama", "chiba", "tokyo", "kanagawa",
	"niigata", "toyama", "ishikawa", "fukui", "yamanashi", "nagano", "gifu", "shizuoka", "aichi",
	"mie", "shiga", "kyoto", "osaka", "hyogo", "nara", "wakayama",
	"tottori", "shimane", "okayama", "hiroshima", "yamaguchi",
	"tokushima", "kagawa", "ehime", "kochi",
	"fukuoka", "saga", "nagasaki", "kumamoto", "oita", "miyazaki", "kagoshima", "okinawa",
];

/*  */
function applyPrefectureFilter() {
	state.selectedPrefectures = new Set(
		PREFECTURE_SLUGS.filter(slug => {
			const cb = document.getElementById("pref-filter-" + slug);
			return cb && cb.checked;
		})
	);
	clearPokelids();
	showPokelids();
	updateCounter();
}

/*  */
function updatePrefectureLabels(locale) {
	document.getElementById("prefecture-title").textContent    = t("ui", "prefecture_panel_title", locale);
	document.getElementById("prefecture-toggle").textContent   = "🗾 " + t("ui", "prefecture_panel_title", locale);

	const allLabel = document.querySelector("label[for='pref-filter-all'] .pref-filter-label-text");
	if (allLabel) allLabel.textContent = t("ui", "filter_all_prefectures", locale);

	PREFECTURE_SLUGS.forEach(slug => {
		const label = document.querySelector(`label[for='pref-filter-${slug}'] .pref-filter-label-text`);
		if (label) label.textContent = t("prefectures", slug, locale);
	});
}

/*  */
function initPrefecturePanel() {
	const panel       = document.getElementById("prefecture-panel");
	const filterPanel = document.getElementById("filter-panel");
	const allCb       = document.getElementById("pref-filter-all");

	document.getElementById("prefecture-toggle").addEventListener("click", () => {
		panel.classList.toggle("open");
		if (filterPanel) filterPanel.classList.remove("open");
	});
	document.getElementById("prefecture-close").addEventListener("click", () => {
		panel.classList.remove("open");
	});

	// "All prefectures" — clear selection
	allCb.addEventListener("change", () => {
		if (allCb.checked) {
			PREFECTURE_SLUGS.forEach(slug => {
				const cb = document.getElementById("pref-filter-" + slug);
				if (cb) cb.checked = false;
			});
			state.selectedPrefectures = new Set();
			clearPokelids();
			showPokelids();
			updateCounter();
		}
	});

	// Individual prefecture checkboxes
	PREFECTURE_SLUGS.forEach(slug => {
		const cb = document.getElementById("pref-filter-" + slug);
		if (!cb) return;
		cb.addEventListener("change", () => {
			if (allCb) allCb.checked = false;
			applyPrefectureFilter();
		});
	});
}
