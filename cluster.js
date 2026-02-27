//
// cluster.js
// @author Sebastian Arana
//

/*  */
function haversineKm(lat1, lng1, lat2, lng2) {
	const R = 6371;
	const dLat = (lat2 - lat1) * Math.PI / 180;
	const dLng = (lng2 - lng1) * Math.PI / 180;
	const a = Math.sin(dLat / 2) ** 2 +
		Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
		Math.sin(dLng / 2) ** 2;
	return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/*  */
function clusterPokelids(points, maxKm = CLUSTER_DISTANCE_KM) {
	const used = new Set();
	return points.reduce((clusters, point, i) => {
		if (used.has(i)) return clusters;
		const lids = [point];
		points.forEach((other, j) => {
			if (i === j || used.has(j)) return;
			if (haversineKm(point.lat, point.lng, other.lat, other.lng) <= maxKm) {
				lids.push(other);
				used.add(j);
			}
		});
		used.add(i);
		const lat = lids.reduce((s, l) => s + l.lat, 0) / lids.length;
		const lng = lids.reduce((s, l) => s + l.lng, 0) / lids.length;
		clusters.push({ lids, lat, lng, prefecture: point.prefecture });
		return clusters;
	}, []);
}

/*  */
function getVisiblePoints() {
	const slugs = state.selectedPrefectures.size > 0
		? state.selectedPrefectures
		: new Set(Object.keys(state.pokelids));
	const points = [];
	for (const slug of slugs) {
		(state.pokelids[slug] ?? []).forEach(p => points.push({ ...p, prefecture: slug }));
	}
	return points;
}
