//
// map.js
// @author Sebastian Arana
//

const regionColors = d3.scaleOrdinal()
	.domain([
		"Hokkaido-Tohoku",
		"Kanto",
		"Chubu",
		"Kinki",
		"Chugoku-Shikoku",
		"Kyushu-Okinawa"
	])
	.range(d3.schemeSet3);

const WIDTH = window.innerWidth;
const HEIGHT = window.innerHeight;
const PADDING = 50;

let selectedPrefectures = new Set();

const projection = d3.geoEquirectangular()
const path = d3.geoPath().projection(projection);
const tooltip = d3.select("#tooltip");

let pokelids = {};
d3.json("pokelids.json").then(data => {
	console.log("Pokelid Data Loaded Successfully:", data);
	pokelids = data; 
});

const svg = d3.select("svg").attr("width", WIDTH).attr("height", HEIGHT)
const g = svg.append("g").attr("width", WIDTH).attr("height", HEIGHT);

const prefLayer = g.append("g").attr("class", "prefectures");
const pokelidLayer = g.append("g").attr("class", "pokelids");
const cityLayer = g.append("g").attr("class", "cities");


const zoom = d3.zoom().scaleExtent([1, 20])
	.on("zoom", (event) => {
		g.attr("transform", event.transform);
	});
svg.call(zoom);


function resetColors() {
	g.selectAll(".prefecture")
		.classed("selected", false)
		.attr("fill", d => {
			const pref = d.properties.name;
			return regionColors(regions[pref]);
		});
	selectedPrefectures.clear();
}

function filterCitiesByPrefecture() {
	cityLayer.selectAll("g.city")
		.style("display", function(d) {
			for (let prefName of selectedPrefectures) {
				const prefFeature = g.selectAll(".prefecture")
					.data()
					.find(f => f.properties.name === prefName);
				if (prefFeature && d3.geoContains(prefFeature, [d.lng, d.lat])) {
					return "block";
				}
			}
			return "none";
		});
}

function showPokelidModal(pokelid) {
	console.log("=== showPokelidModal called ===");
	console.log("Pokelid:", pokelid);
	
	const modal = d3.select("#pokelid-modal");
	const prefecture = pokelid.prefecture;
	
	console.log("Modal element:", modal.node());
	console.log("Classes before:", modal.attr("class"));

	// Set modal content
	modal.select(".modal-title").text(pokelid.name);
	modal.select(".modal-prefecture").text(prefecture);

	// Set prefecture image
	const imagePath = `backgrounds/Location_Background_Pokelid_${prefecture}.png`;
	modal.select(".modal-image")
		.attr("src", imagePath)
		.attr("alt", `${prefecture} Pokélid`);

	// Set Google Maps link
	const mapsUrl = `https://www.google.com/maps?q=${pokelid.lat},${pokelid.lng}`;
	modal.select(".modal-maps-link")
		.attr("href", mapsUrl);

	// Set Pokemon Local Acts link
	const pokemonUrl = `https://local.pokemon.jp/en/manhole/${prefecture.toLowerCase()}.html`;
	modal.select(".modal-pokemon-link")
		.attr("href", pokemonUrl);

	// Show modal
	modal.node().style.display = ''; // Remove inline style
	modal.classed("show", true);
	
	console.log("Classes after:", modal.attr("class"));
	console.log("Computed display:", window.getComputedStyle(modal.node()).display);
	console.log("=== End showPokelidModal ===");
}

function closePokelidModal() {
	const modal = d3.select("#pokelid-modal");
	modal.classed("show", false);
	modal.node().style.display = 'none'; // Force hide with inline style
	console.log("Modal closed");
}

function showClusterModal(cluster) {
	console.log("=== showClusterModal called ===");
	console.log("Cluster with", cluster.lids.length, "lids");
	
	const modal = d3.select("#cluster-modal");
	const prefecture = cluster.prefecture;
	
	// Set modal title
	modal.select(".cluster-modal-title").text(`${cluster.lids.length} Pokélids in ${prefecture}`);
	
	// Clear and populate list
	const listContainer = modal.select(".cluster-list");
	listContainer.html(""); // Clear existing
	
	cluster.lids.forEach(lid => {
		const item = listContainer.append("div")
			.attr("class", "cluster-item")
			.style("cursor", "pointer")
			.on("click", function() {
				closeClusterModal();
				showPokelidModal(lid);
			});
		
		item.append("div")
			.attr("class", "cluster-item-name")
			.text(lid.name);
		
		item.append("div")
			.attr("class", "cluster-item-coords")
			.text(lid.dms);
	});
	
	// Show modal
	modal.node().style.display = '';
	modal.classed("show", true);
	console.log("=== End showClusterModal ===");
}

function closeClusterModal() {
	const modal = d3.select("#cluster-modal");
	modal.classed("show", false);
	modal.node().style.display = 'none';
	console.log("Cluster modal closed");
}

// Calculate distance between two lat/lng points in km
function getDistance(lat1, lng1, lat2, lng2) {
	const R = 6371; // Earth's radius in km
	const dLat = (lat2 - lat1) * Math.PI / 180;
	const dLng = (lng2 - lng1) * Math.PI / 180;
	const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
	          Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
	          Math.sin(dLng/2) * Math.sin(dLng/2);
	const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
	return R * c;
}

// Cluster nearby pokelids within 5km
function clusterPokelids(points, maxDistance = 5) {
	const clusters = [];
	const used = new Set();
	
	points.forEach((point, i) => {
		if (used.has(i)) return;
		
		const cluster = {
			lids: [point],
			lat: point.lat,
			lng: point.lng,
			prefecture: point.prefecture
		};
		
		// Find all points within maxDistance km
		points.forEach((other, j) => {
			if (i === j || used.has(j)) return;
			const distance = getDistance(point.lat, point.lng, other.lat, other.lng);
			if (distance <= maxDistance) {
				cluster.lids.push(other);
				used.add(j);
			}
		});
		
		used.add(i);
		
		// Calculate centroid if multiple lids
		if (cluster.lids.length > 1) {
			cluster.lat = cluster.lids.reduce((sum, lid) => sum + lid.lat, 0) / cluster.lids.length;
			cluster.lng = cluster.lids.reduce((sum, lid) => sum + lid.lng, 0) / cluster.lids.length;
		}
		
		clusters.push(cluster);
	});
	
	return clusters;
}

function showPokelids() {
	const allPoints = [];
	for (let prefName of selectedPrefectures) {
		const points = pokelids[prefName] || [];
		points.forEach(p => {
			allPoints.push({...p, prefecture: prefName});
		});
	}
	
	// Cluster nearby pokelids
	const clusters = clusterPokelids(allPoints, 5);
	
	// Remove old clusters
	pokelidLayer.selectAll("g.pokelid-cluster").remove();
	
	// Create cluster groups
	const clusterGroups = pokelidLayer.selectAll("g.pokelid-cluster")
		.data(clusters, d => `${d.prefecture}-${d.lat},${d.lng}-${d.lids.length}`);
	
	const enterGroups = clusterGroups.enter()
		.append("g")
		.attr("class", "pokelid-cluster")
		.style("cursor", "pointer");
	
	// Add circles to groups
	enterGroups.append("circle")
		.attr("class", "pokelid-circle")
		.attr("r", d => d.lids.length > 1 ? 1.2 : 0.75)
		.attr("fill", d => d.lids.length > 1 ? "#ff6b6b" : "red")
		.attr("stroke", "black")
		.attr("stroke-width", 0.25)
		.attr("opacity", 0.9);
	
	// Add count badge for clusters with multiple lids
	enterGroups.filter(d => d.lids.length > 1)
		.append("text")
		.attr("class", "cluster-count")
		.attr("text-anchor", "middle")
		.attr("dy", "0.35em")
		.attr("font-size", "2.5px")
		.attr("font-weight", "bold")
		.attr("fill", "white")
		.attr("stroke", "black")
		.attr("stroke-width", 0.15)
		.attr("paint-order", "stroke")
		.text(d => d.lids.length);
	
	// Position and add events to merged selection
	enterGroups.merge(clusterGroups)
		.attr("transform", d => {
			const [x, y] = projection([d.lng, d.lat]);
			return `translate(${x}, ${y})`;
		})
		.on("mousemove touchmove", function(event, d) {
			const e = event.type === 'touchmove' ? event.touches[0] : event;
			const tooltipText = d.lids.length > 1 
				? `${d.lids.length} Pokélids in this area`
				: `${d.lids[0].name}<br>${d.lids[0].dms}`;
			tooltip.style("opacity", 1)
				.html(tooltipText)
				.style("left", (e.pageX + 12) + "px")
				.style("top", (e.pageY + 12) + "px");
		})
		.on("mouseout touchend", function() {
			tooltip.style("opacity", 0);
		})
		.on("click touchend", function(event, d) {
			console.log("*** Cluster clicked! ***", d);
			event.stopPropagation();
			event.preventDefault();
			
			// Only trigger on actual clicks, not drags
			if (event.type === 'touchend') {
				const touch = event.changedTouches[0];
				const elem = document.elementFromPoint(touch.clientX, touch.clientY);
				if (!this.contains(elem) && elem !== this) return;
			}
			
			// If single lid, show its modal
			if (d.lids.length === 1) {
				showPokelidModal(d.lids[0]);
			} else {
				// If cluster, show list modal
				showClusterModal(d);
			}
		});
	
	clusterGroups.exit().remove();
}

function clearPokelids() {
	pokelidLayer.selectAll("g.pokelid-cluster").remove();
}

const customZoomBounds = {
	// fix to tokyo mainland
	"Tokyo": {
		lat: [35.5, 35.85],
		lng: [139.3, 139.9]
	}
}

function zoomToSelection() {
	if (selectedPrefectures.size === 0) {
		svg.transition()
			.duration(750)
			.call(zoom.transform, d3.zoomIdentity);
		return;
	}

	const selectedFeatures = g.selectAll(".prefecture")
		.data()
		.filter(f => selectedPrefectures.has(f.properties.name));

	if (selectedFeatures.length === 0) return;

	let minX = Infinity, minY = Infinity;
	let maxX = -Infinity, maxY = -Infinity;
	selectedFeatures.forEach(feature => {
		const prefName = feature.properties.name;
		
		if (customZoomBounds[prefName]) {
			const custom = customZoomBounds[prefName];
			const [x0, y0] = projection([custom.lng[0], custom.lat[1]]);
			const [x1, y1] = projection([custom.lng[1], custom.lat[0]]);
			minX = Math.min(minX, x0);
			minY = Math.min(minY, y0);
			maxX = Math.max(maxX, x1);
			maxY = Math.max(maxY, y1);
		} else {
			const [[x0, y0], [x1, y1]] = path.bounds(feature);
			minX = Math.min(minX, x0);
			minY = Math.min(minY, y0);
			maxX = Math.max(maxX, x1);
			maxY = Math.max(maxY, y1);
		}
	});
	const scale = Math.min(10, 0.8 / Math.max((maxX - minX) / WIDTH, (maxY - minY) / HEIGHT));
	const centerX = (minX + maxX) / 2;
	const centerY = (minY + maxY) / 2;

	svg.transition()
		.duration(750)
		.call(
			zoom.transform,
			d3.zoomIdentity
				.translate(WIDTH / 2, HEIGHT / 2)
				.scale(scale)
				.translate(-centerX, -centerY)
		);
}

d3.json("jp.json").then(function(geojson) {
	projection.fitExtent([[PADDING, PADDING],[WIDTH - PADDING, HEIGHT - PADDING]],geojson);
	g.selectAll(".prefecture")
		.data(geojson.features)
		.join("path")
		.attr("class", "prefecture")
		.attr("d", path)
		.attr("fill", d => {
			const pref = d.properties.name;
			const region = regions[pref];
			return regionColors(region);
		})
		.style("cursor", "pointer")
		.on("mousemove touchmove", function (event, d) {
			// Handle both mouse and touch events
			const e = event.type === 'touchmove' ? event.touches[0] : event;
			tooltip.style("opacity", 1)
				.html(d.properties.name)
				.style("left", (e.pageX + 12) + "px")
				.style("top", (e.pageY + 12) + "px");
		})
		.on("mouseout touchend", function () {
			tooltip.style("opacity", 0);
		})
		.on("click touchend", function (event, d) {
			event.stopPropagation();
			event.preventDefault(); // Prevent double-tap zoom on mobile
			
			// Only trigger on actual clicks, not drags
			if (event.type === 'touchend') {
				const touch = event.changedTouches[0];
				const elem = document.elementFromPoint(touch.clientX, touch.clientY);
				if (elem !== this) return; // Touch ended on different element
			}
			
			const prefName = d.properties.name;
			
			// Toggle selection
			if (selectedPrefectures.has(prefName)) {
				selectedPrefectures.delete(prefName);
				d3.select(this).classed("selected", false);
			} else {
				selectedPrefectures.add(prefName);
				d3.select(this).classed("selected", true);
			}

			clearPokelids();
			showPokelids();
			filterCitiesByPrefecture();
			zoomToSelection();

			console.log("Selected prefectures:", Array.from(selectedPrefectures));
		});		
	pokelidLayer.raise();
	cityLayer.raise();
	
	// Load cities AFTER projection is configured
	d3.json("jpcities.json").then(function(cities) {
		cityLayer.selectAll("g.city")
			.data(cities)
			.join("g")
				.attr("class", "city")
				.style("display", "none")
				.each(function(d) {
					const group = d3.select(this);
					group.append("circle")
						.attr("r", 0.5)
						.attr("fill", "#000")
						.attr("stroke", "#fff")
						.attr("stroke-width", 0.25);
		
					group.append("text")
						.text(d.city)
						.attr("x", 1)
						.attr("y", 1)
						.attr("font-size", "3px")
						.attr("font-family", "sans-serif")
						.attr("fill", "#333")
						.attr("paint-order", "stroke")
						.attr("stroke", "white")
						.attr("stroke-width", 0.5)
						.style("pointer-events", "none");
				})
				.attr("transform", d => {
					const [x, y] = projection([+d.lng, +d.lat]);
					return `translate(${x},${y})`;
				});
	});
});

svg.on("click", () => {
	resetColors();
	clearPokelids();
	cityLayer.selectAll("g.city")
		.style("display", "none");
	svg.transition()
		.duration(750)
		.call(zoom.transform, d3.zoomIdentity);
});

d3.select("#pokelid-modal").on("click", function(event) {
	if (event.target === this) {
		closePokelidModal();
	}
});
d3.select(".modal-close").on("click", function(event) {
	event.stopPropagation();
	closePokelidModal();
});

// Cluster modal event handlers
d3.select("#cluster-modal").on("click", function(event) {
	if (event.target === this) {
		closeClusterModal();
	}
});
d3.select(".cluster-modal-close").on("click", function(event) {
	event.stopPropagation();
	closeClusterModal();
});
