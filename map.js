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

function showPokelids() {
	const allPoints = [];
	for (let prefName of selectedPrefectures) {
		const points = pokelids[prefName] || [];
		points.forEach(p => {
			allPoints.push({...p, prefecture: prefName});
		});
	}
	const circles = pokelidLayer.selectAll("circle.pokelid")
		.data(allPoints, d => `${d.prefecture}-${d.lat},${d.lng}`);

	circles.enter()
		.append("circle")
		.attr("class", "pokelid")
		.attr("r", 0.75)
		.attr("fill", "red")
		.attr("stroke", "black")
		.attr("stroke-width", 0.25)
		.attr("opacity", 0.9)
		.attr("transform", d => {
			const [x,y] = projection([d.lng, d.lat]);
			return `translate(${x}, ${y})`;
		})
		.on("mousemove", function(event, d) {
			tooltip.style("opacity", 1)
				.html(`${d.name}<br>${d.dms}`)
				.style("left", (event.pageX + 12) + "px")
				.style("top", (event.pageY + 12) + "px");
		})
		.on("mouseout", function() {
			tooltip.style("opacity", 0);
		});

	circles.exit().remove();
}

function clearPokelids() {
	pokelidLayer.selectAll(".pokelid").remove();
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
		.on("mousemove", function (event, d) {
			tooltip.style("opacity", 1)
				.html(d.properties.name)
				.style("left", (event.pageX + 12) + "px")
				.style("top", (event.pageY + 12) + "px");
		})
		.on("mouseout", function () {
			tooltip.style("opacity", 0);
		})
		.on("click", function (event, d) {
			event.stopPropagation();
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
});

d3.json("jpcities.json").then(function(cities) {
	cityLayer.selectAll("g.city")
		.data(cities)
		.join("g")
			.attr("class", "city")
			.style("display", "none")
			.attr("transform", d => {
				const [x, y] = projection([+d.lng, +d.lat]);
				return `translate(${x},${y})`;
			})
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

