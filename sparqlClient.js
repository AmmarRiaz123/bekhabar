const ENDPOINT = "https://genotypical-mao-coxal.ngrok-free.dev/repositories/new-fifa"; // replace with your endpoint

const HEADERS = {
  "Content-Type": "application/sparql-query",
  "Accept": "application/sparql-results+json"
};

const LANG = "en";
const LIMIT_SEARCH = 20;
const LIMIT_RELATIONS = 50;

async function runQuery(query) {
  const res = await fetch(ENDPOINT, {
    method: "POST",
    headers: HEADERS,
    body: query
  });
  if (!res.ok) throw new Error(`SPARQL error ${res.status}`);
  const json = await res.json();
  return json.results.bindings;
}

const q = {
  search: term => `
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?uri ?label WHERE {
      ?uri rdfs:label ?label .
      FILTER (langMatches(lang(?label), "${LANG}"))
      FILTER (CONTAINS(LCASE(STR(?label)), LCASE("${term.replace(/"/g, '\\"')}")))
    } LIMIT ${LIMIT_SEARCH}
  `,
  entityDetails: uri => `
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?label ?comment ?type ?typeLabel WHERE {
      OPTIONAL { <${uri}> rdfs:label ?label FILTER (langMatches(lang(?label), "${LANG}")) }
      OPTIONAL { <${uri}> rdfs:comment ?comment FILTER (langMatches(lang(?comment), "${LANG}")) }
      OPTIONAL { <${uri}> rdf:type ?type . OPTIONAL { ?type rdfs:label ?typeLabel FILTER (langMatches(lang(?typeLabel), "${LANG}")) } }
    } LIMIT ${LIMIT_RELATIONS}
  `,
  outgoing: uri => `
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?p ?pLabel ?o ?oLabel WHERE {
      <${uri}> ?p ?o .
      FILTER (isIRI(?o))
      OPTIONAL { ?p rdfs:label ?pLabel FILTER (langMatches(lang(?pLabel), "${LANG}")) }
      OPTIONAL { ?o rdfs:label ?oLabel FILTER (langMatches(lang(?oLabel), "${LANG}")) }
    } LIMIT ${LIMIT_RELATIONS}
  `,
  incoming: uri => `
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?s ?sLabel ?p ?pLabel WHERE {
      ?s ?p <${uri}> .
      FILTER (isIRI(?s))
      OPTIONAL { ?p rdfs:label ?pLabel FILTER (langMatches(lang(?pLabel), "${LANG}")) }
      OPTIONAL { ?s rdfs:label ?sLabel FILTER (langMatches(lang(?sLabel), "${LANG}")) }
    } LIMIT ${LIMIT_RELATIONS}
  `
};

const val = (binding, key) => binding[key]?.value;
const labelOrUri = (binding, labelKey, uriKey) => val(binding, labelKey) || val(binding, uriKey);

export async function searchEntities(term) {
  if (!term.trim()) return [];
  const rows = await runQuery(q.search(term.trim()));
  return rows.map(r => ({ uri: val(r, "uri"), label: labelOrUri(r, "label", "uri") }));
}

export async function getEntityDetails(uri) {
  const [details, outgoing, incoming] = await Promise.all([
    runQuery(q.entityDetails(uri)),
    runQuery(q.outgoing(uri)),
    runQuery(q.incoming(uri))
  ]);

  const first = details[0] || {};
  const label = labelOrUri(first, "label", null) || uri;
  const comment = val(first, "comment") || "";
  const types = details
    .map(r => ({
      uri: val(r, "type"),
      label: labelOrUri(r, "typeLabel", "type")
    }))
    .filter(t => t.uri);

  const outgoingRels = outgoing.map(r => ({
    predicate: val(r, "p"),
    predicateLabel: labelOrUri(r, "pLabel", "p"),
    object: val(r, "o"),
    objectLabel: labelOrUri(r, "oLabel", "o")
  }));

  const incomingRels = incoming.map(r => ({
    subject: val(r, "s"),
    subjectLabel: labelOrUri(r, "sLabel", "s"),
    predicate: val(r, "p"),
    predicateLabel: labelOrUri(r, "pLabel", "p")
  }));

  return { label, comment, types, outgoingRels, incomingRels };
}
