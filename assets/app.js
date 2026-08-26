let map;
let droughtLayer;
let historyChart;
let latestGovData = {}; 
let nameLookup = {}; 

const tunisiaAliases = {
    "elkef": "kef",
    "alkef": "kef",
    "medenine": "medenine",
    "madanin": "medenine",
    "mednin": "medenine",
    "mednine": "medenine",
    "gabes": "gabes",
    "qabis": "gabes",
    "beja": "beja",
    "bja": "beja",
    "kebili": "kebili",
    "qibili": "kebili",
    "gbili": "kebili",
    "kasserine": "kasserine",
    "gasrine": "kasserine",
    "alqasrayn": "kasserine",
    "tataouine": "tataouine",
    "tatawin": "tataouine",
    "kairouan": "kairouan",
    "qairawan": "kairouan",
    "sfax": "sfax",
    "safaqis": "sfax",
    "sousse": "sousse",
    "susa": "sousse",
    "bizerte": "bizerte",
    "banzart": "bizerte",
    "benarous": "benarous",
    "binarus": "benarous",
    "sidi bouzid": "sidibouzid",
    "sidibuzid": "sidibouzid",
    "ariana": "ariana",
    "aryanah": "ariana",
    "tozeur": "tozeur",
    "tawzar": "tozeur",
    "gafsa": "gafsa",
    "qafsah": "gafsa",
    "mahdia": "mahdia",
    "mahdiyya": "mahdia",
    "nabeul": "nabeul",
    "nabul": "nabeul",
    "zaghouan": "zaghouan",
    "zaghwan": "zaghouan",
    "manouba": "manouba",
    "manuba": "manouba",
    "siliana": "siliana",
    "jendouba": "jendouba",
    "tunis": "tunis"
};

initializeMap();
loadDashboard();

function initializeMap(){
    map = L.map("map").setView([34.1, 9.5], 7);
    L.tileLayer(
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        { attribution: "© OpenStreetMap" }
    ).addTo(map);
}

function getClassColor(classification){
    switch(classification){
        case "Extreme": return "#7f0000";
        case "Severe": return "#d73027";
        case "Moderate": return "#fc8d59";
        case "Watch": return "#fee08b";
        default: return "#91cf60";
    }
}

// STRIPS ACCENTS AND FINDS THE TRUE NAME
function normalizeGovName(rawName) {
    if (!rawName) return "";
    let cleanName = String(rawName)
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]/g, '');
        
    return tunisiaAliases[cleanName] || cleanName;
}

// LOOKS FOR HARDCODED IDs LIKE TN_01
function getAggressiveId(properties) {
    for (let key in properties) {
        let val = String(properties[key]).trim();
        if (val.match(/^TN_\d{2}$/i)) return val.toUpperCase();
    }
    const idKeys = ['website_id', 'website_id_x', 'id', 'id_1', 'hasc_1', 'adm1_pcode', 'ref'];
    for (let key of idKeys) {
        for (let prop in properties) {
            if (prop.toLowerCase() === key) {
                let val = String(properties[prop]).trim();
                if (val.match(/^\d+$/)) return "TN_" + val.padStart(2, '0'); 
            }
        }
    }
    return null;
}

async function loadDashboard(){
    try {
        const latest = await fetch("./output/latest.json").then(r => r.json());
        
        const dispDate = latest.latest_date || latest.date || latest.Date || "Unknown Date";
        document.getElementById("latest-date").innerText = dispDate;
        
        document.getElementById("gov-count").innerText = latest.summary?.governorates || 0;
        document.getElementById("severe-count").innerText = latest.summary?.severe_or_extreme_governorates || 0;
        document.getElementById("affected-cropland").innerText = Math.round(latest.summary?.cropland_affected_km2 || 0).toLocaleString() + " km²";

        if (latest.governorates) {
            latest.governorates.forEach(gov => {
                if (gov.website_id) {
                    latestGovData[String(gov.website_id).toUpperCase().trim()] = gov;
                }
                if (gov.name || gov.governorate_name) {
                    const normName = normalizeGovName(gov.name || gov.governorate_name);
                    nameLookup[normName] = gov;
                }
            });
        }
    } catch (e) {
        console.error("Error loading ./output/latest.json", e);
    }

    try {
        const geojson = await fetch("./output/governorates_latest.geojson").then(r => r.json());
        
        droughtLayer = L.geoJSON(geojson, {
            style: function(feature){
                const wid = getAggressiveId(feature.properties);
                const rawName = feature.properties.governorate_name || feature.properties.shape1 || feature.properties.name_en || "";
                const normName = normalizeGovName(rawName);
                
                const masterData = latestGovData[(wid || "").toUpperCase()] || nameLookup[normName] || {};
                const govData = { ...feature.properties, ...masterData };
                
                return {
                    fillColor: getClassColor(govData.drought_class),
                    weight: 1,
                    color: "#444",
                    fillOpacity: 0.75
                };
            },
            onEachFeature: function(feature, layer){
                const rawName = feature.properties.governorate_name || feature.properties.shape1 || feature.properties.name_en || "Unknown";
                layer.bindTooltip(rawName);
                
                layer.on("mouseover", function(){
                    layer.setStyle({ weight: 3 });
                });
                
                layer.on("mouseout", function(){
                    droughtLayer.resetStyle(layer);
                });
                
                layer.on("click", function(){
                    loadGovernorate(feature.properties);
                });
            }
        }).addTo(map);
    } catch (e) {
        console.error("Error loading ./output/governorates_latest.geojson", e);
    }
}

async function loadGovernorate(featureProps){
    const rawName = featureProps.governorate_name || featureProps.shape1 || featureProps.name_en || "Unknown";
    const normName = normalizeGovName(rawName);
    const possibleId = getAggressiveId(featureProps);
    
    // 1. Get fallback data from the National Summary
    const masterData = latestGovData[(possibleId || "").toUpperCase()] || nameLookup[normName] || {};
    const finalGovId = (masterData.website_id || possibleId || "").toUpperCase().trim();

    let gov = {};

    // 2. Fetch specific data and merge it all together
    try {
        if (!finalGovId) throw new Error("No ID available to fetch");
        let fetchedData = await fetch("./output/governorates/" + finalGovId + ".json").then(r => r.json());
        
        // Safety check: if the JSON is an array, grab the first item
        if (Array.isArray(fetchedData)) {
            fetchedData = fetchedData[0];
        }
        // Safety check: if data is nested inside "properties"
        if (fetchedData && fetchedData.properties) {
            fetchedData = fetchedData.properties;
        }

        // Merge Map Data + Summary Data + Specific File Data
        gov = { ...featureProps, ...masterData, ...fetchedData };
        
    } catch (e) {
        // If the specific file fails, merge just the Map Data + Summary Data
        gov = { ...featureProps, ...masterData };
    }

    const displayTitle = gov.name || gov.governorate_name || rawName;

    // Update text panel
    document.getElementById("gov-panel").innerHTML = `
        <h2>${displayTitle}</h2>
        <table>
        <tr><td>Drought Class</td><td>${gov.drought_class || "N/A"}</td></tr>
        <tr><td>Hazard Score</td><td>${Number(gov.hazard_score || 0).toFixed(2)}</td></tr>
        <tr><td>Risk Score</td><td>${Number(gov.risk_score || 0).toFixed(2)}</td></tr>
        <tr><td>Exposure Score</td><td>${Number(gov.exposure_score || 0).toFixed(2)}</td></tr>
        <tr><td>Vulnerability Score</td><td>${Number(gov.vulnerability_score || 0).toFixed(2)}</td></tr>
        <tr><td>Trend</td><td>${gov.drought_trend || "N/A"}</td></tr>
        <tr><td>Persistence</td><td>${gov.drought_persistence_months || 0} months</td></tr>
        <tr><td>Population Exposed</td><td>${Number(gov.population_exposed || 0).toLocaleString()}</td></tr>
        <tr><td>Cropland Affected</td><td>${Number(gov.cropland_affected_km2 || 0).toLocaleString()} km²</td></tr>
        </table>
    `;

    // Fetch and draw chart
    try {
        if (!finalGovId) throw new Error("No ID available to fetch chart");
        
        const data = await fetch("./output/timeseries/" + finalGovId + ".json").then(r => r.json());
        
        let historicalData = [];
        if (Array.isArray(data)) {
            historicalData = data;
        } else if (data.historical) {
            historicalData = data.historical;
        }

        if (historicalData.length > 0) {
            loadTimeSeriesChart(historicalData);
        } else {
            document.getElementById("chart-container").innerHTML = "<canvas id='historyChart'></canvas>";
        }
        
    } catch (e) {
        console.error("Error loading chart for " + displayTitle, e);
        document.getElementById("chart-container").innerHTML = "<canvas id='historyChart'></canvas>";
    }
}

function loadTimeSeriesChart(historicalData){
    if (!document.getElementById("historyChart")) {
        document.getElementById("chart-container").innerHTML = "<canvas id='historyChart'></canvas>";
    }
    
    if (historyChart) {
        historyChart.destroy();
    }

    const labels = historicalData.map(x => x.date);
    const hazard = historicalData.map(x => x.hazard_score);

    const ctx = document.getElementById("historyChart").getContext("2d");
    historyChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Hazard Score",
                data: hazard,
                borderWidth: 2,
                tension: 0.2,
                borderColor: '#1f2937',
                backgroundColor: 'rgba(31, 41, 55, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, max: 1 }
            }
        }
    });
}
