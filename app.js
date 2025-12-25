import { searchEntities, getEntityDetails } from "./sparqlClient.js";

const searchInput = document.getElementById("searchInput");
const searchResults = document.getElementById("searchResults");
const entityLabelEl = document.getElementById("entityLabel");
const entityCommentEl = document.getElementById("entityComment");
const entityTypesEl = document.getElementById("entityTypes");
const outgoingList = document.getElementById("outgoingList");
const incomingList = document.getElementById("incomingList");
const graphSvg = d3.select("#graphSvg");

let currentURI = null;
let searchTimeout;

const debounce = (fn, ms = 250) => (...args) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => fn(...args), ms);
};

searchInput.addEventListener("input", debounce(onSearch));

async function onSearch() {
  const term = searchInput.value;
  if (!term.trim()) {
    searchResults.innerHTML = "";
    return;
  }
  try {
    const hits = await searchEntities(term);
    searchResults.innerHTML = hits
      .map(hit => `<li data-uri="${hit.uri}">${hit.label}</li>`)
      .join("");
  } catch (e) {
    console.error(e);
  }
}

searchResults.addEventListener("click", e => {
  const li = e.target.closest("li[data-uri]");
  if (!li) return;
  selectEntity(li.dataset.uri);
  searchResults.innerHTML = "";
  searchInput.value = li.textContent;
});

async function selectEntity(uri) {
  currentURI = uri;
  entityLabelEl.textContent = "Loading…";
  entityCommentEl.textContent = "";
  outgoingList.innerHTML = "";
  incomingList.innerHTML = "";
  try {
    const data = await getEntityDetails(uri);
    renderDetails(uri, data);
    renderGraph(uri, data);
  } catch (e) {
    entityLabelEl.textContent = "Failed to load entity";
    console.error(e);
  }
}

function renderDetails(uri, data) {
  entityLabelEl.textContent = data.label || uri;
  entityCommentEl.textContent = data.comment || "No description available.";
  entityTypesEl.innerHTML = data.types
    .map(t => `<span class="badge" title="${t.uri}">${t.label}</span>`)
    .join("");

  outgoingList.innerHTML = data.outgoingRels
    .map(r => `<li><strong>${r.predicateLabel}</strong> → <a href="#" data-uri="${r.object}">${r.objectLabel}</a></li>`)
    .join("");

  incomingList.innerHTML = data.incomingRels
    .map(r => `<li><a href="#" data-uri="${r.subject}">${r.subjectLabel}</a> → <strong>${r.predicateLabel}</strong></li>`)
    .join("");
}

[outgoingList, incomingList].forEach(list => {
  list.addEventListener("click", e => {
    const link = e.target.closest("a[data-uri]");
    if (link) {
      e.preventDefault();
      selectEntity(link.dataset.uri);
    }
  });
});

function renderGraph(uri, data) {
  const nodes = [{ id: uri, label: data.label || uri, central: true }];
  const links = [];

  data.outgoingRels.forEach(r => {
    nodes.push({ id: r.object, label: r.objectLabel });
    links.push({ source: uri, target: r.object, label: r.predicateLabel });
  });

  data.incomingRels.forEach(r => {
    nodes.push({ id: r.subject, label: r.subjectLabel });
    links.push({ source: r.subject, target: uri, label: r.predicateLabel });
  });

  const uniq = new Map();
  nodes.forEach(n => uniq.set(n.id, n));
  const uniqueNodes = Array.from(uniq.values());

  graphSvg.selectAll("*").remove();
  const width = +graphSvg.attr("width");
  const height = +graphSvg.attr("height");

  const simulation = d3.forceSimulation(uniqueNodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(120))
    .force("charge", d3.forceManyBody().strength(-250))
    .force("center", d3.forceCenter(width / 2, height / 2));

  const link = graphSvg.append("g")
    .selectAll("line")
    .data(links)
    .enter()
    .append("line")
    .attr("stroke", "#cbd2d9")
    .attr("stroke-width", 1.5);

  const edgeLabels = graphSvg.append("g")
    .selectAll("text")
    .data(links)
    .enter()
    .append("text")
    .attr("fill", "#52606d")
    .text(d => d.label);

  const node = graphSvg.append("g")
    .selectAll("circle")
    .data(uniqueNodes)
    .enter()
    .append("circle")
    .attr("r", d => d.central ? 12 : 8)
    .attr("fill", d => d.central ? "#0f62fe" : "#9fb3c8")
    .call(drag(simulation))
    .on("click", (_, d) => selectEntity(d.id));

  const labels = graphSvg.append("g")
    .selectAll("text")
    .data(uniqueNodes)
    .enter()
    .append("text")
    .attr("dy", -12)
    .attr("text-anchor", "middle")
    .text(d => d.label);

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);

    labels
      .attr("x", d => d.x)
      .attr("y", d => d.y);

    edgeLabels
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2);
  });
}

function drag(simulation) {
  return d3.drag()
    .on("start", event => {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    })
    .on("drag", event => {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    })
    .on("end", event => {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    });
}

// Optionally preload a default entity:
// selectEntity("http://example.com/resource/YourEntity");
