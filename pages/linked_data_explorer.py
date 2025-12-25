import requests
import streamlit as st

st.set_page_config(page_title="Linked Data Explorer", page_icon="🧭", layout="wide")

def run_query(endpoint: str, query: str):
    headers = {"Accept": "application/sparql-results+json", "Content-Type": "application/sparql-query"}
    resp = requests.post(endpoint, data=query.encode("utf-8"), headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", {}).get("bindings", [])

def binding_val(b, key):
    return b.get(key, {}).get("value")

def query_search(term, lang, limit):
    safe_term = term.replace('"', '\\"')
    return f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?uri ?label WHERE {{
  ?uri rdfs:label ?label .
  FILTER(langMatches(lang(?label), "{lang}"))
  FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{safe_term}")))
}} LIMIT {limit}
"""

def query_details(uri, lang, limit):
    return f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?label ?comment ?type ?typeLabel WHERE {{
  OPTIONAL {{ <{uri}> rdfs:label ?label FILTER(langMatches(lang(?label), "{lang}")) }}
  OPTIONAL {{ <{uri}> rdfs:comment ?comment FILTER(langMatches(lang(?comment), "{lang}")) }}
  OPTIONAL {{ <{uri}> rdf:type ?type .
             OPTIONAL {{ ?type rdfs:label ?typeLabel FILTER(langMatches(lang(?typeLabel), "{lang}")) }} }}
}} LIMIT {limit}
"""

def query_outgoing(uri, lang, limit):
    return f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?p ?pLabel ?o ?oLabel WHERE {{
  <{uri}> ?p ?o .
  FILTER(isIRI(?o))
  OPTIONAL {{ ?p rdfs:label ?pLabel FILTER(langMatches(lang(?pLabel), "{lang}")) }}
  OPTIONAL {{ ?o rdfs:label ?oLabel FILTER(langMatches(lang(?oLabel), "{lang}")) }}
}} LIMIT {limit}
"""

def query_incoming(uri, lang, limit):
    return f"""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?s ?sLabel ?p ?pLabel WHERE {{
  ?s ?p <{uri}> .
  FILTER(isIRI(?s))
  OPTIONAL {{ ?p rdfs:label ?pLabel FILTER(langMatches(lang(?pLabel), "{lang}")) }}
  OPTIONAL {{ ?s rdfs:label ?sLabel FILTER(langMatches(lang(?sLabel), "{lang}")) }}
}} LIMIT {limit}
"""

def search_entities(endpoint, term, lang, limit):
    rows = run_query(endpoint, query_search(term, lang, limit))
    return [{"uri": binding_val(r, "uri"), "label": binding_val(r, "label") or binding_val(r, "uri")} for r in rows]

def get_entity(endpoint, uri, lang, limit):
    details = run_query(endpoint, query_details(uri, lang, limit))
    outgoing = run_query(endpoint, query_outgoing(uri, lang, limit))
    incoming = run_query(endpoint, query_incoming(uri, lang, limit))
    first = details[0] if details else {}
    label = binding_val(first, "label") or uri
    comment = binding_val(first, "comment") or ""
    types = [
        {"uri": binding_val(r, "type"), "label": binding_val(r, "typeLabel") or binding_val(r, "type")}
        for r in details if binding_val(r, "type")
    ]
    outgoing_rels = [{
        "predicate": binding_val(r, "p"),
        "predicateLabel": binding_val(r, "pLabel") or binding_val(r, "p"),
        "object": binding_val(r, "o"),
        "objectLabel": binding_val(r, "oLabel") or binding_val(r, "o")
    } for r in outgoing]
    incoming_rels = [{
        "subject": binding_val(r, "s"),
        "subjectLabel": binding_val(r, "sLabel") or binding_val(r, "s"),
        "predicate": binding_val(r, "p"),
        "predicateLabel": binding_val(r, "pLabel") or binding_val(r, "p")
    } for r in incoming]
    return {"label": label, "comment": comment, "types": types, "outgoing": outgoing_rels, "incoming": incoming_rels}

def graph_dot(center_uri, center_label, outgoing, incoming):
    def esc(txt): return (txt or "").replace('"', '\\"')
    lines = [
        'digraph G {',
        '  rankdir=LR;',
        '  node [shape=ellipse, style=filled, color="#0f62fe22", fontname="Arial"];',
        f'  "{esc(center_uri)}" [label="{esc(center_label)}", fillcolor="#0f62fe55", style="filled,bold"];'
    ]
    for rel in outgoing:
        lines.append(f'  "{esc(center_uri)}" -> "{esc(rel["object"])}" [label="{esc(rel["predicateLabel"])}"];')
        lines.append(f'  "{esc(rel["object"])}" [label="{esc(rel["objectLabel"])}"];')
    for rel in incoming:
        lines.append(f'  "{esc(rel["subject"])}" -> "{esc(center_uri)}" [label="{esc(rel["predicateLabel"])}"];')
        lines.append(f'  "{esc(rel["subject"])}" [label="{esc(rel["subjectLabel"])}"];')
    lines.append("}")
    return "\n".join(lines)

st.title("Linked Data Explorer 🧭")
st.caption("Search by label, inspect an entity, browse relations, and view a small graph — without writing SPARQL.")

ENDPOINT = "https://genotypical-mao-coxal.ngrok-free.dev/repositories/new-fifa"

with st.sidebar:
    st.caption(f"Endpoint: `{ENDPOINT}` (fixed)")
    lang = st.text_input("Language tag", value="en")
    limit_search = st.number_input("Search LIMIT", min_value=1, max_value=200, value=20)
    limit_rel = st.number_input("Relations LIMIT", min_value=10, max_value=500, value=50)

with st.form("search_form", clear_on_submit=False):
    term = st.text_input("Search entities by rdfs:label", "")
    submitted = st.form_submit_button("Search")

hits = []
if submitted and term.strip():
    with st.spinner("Searching..."):
        try:
            hits = search_entities(ENDPOINT, term.strip(), lang.strip(), int(limit_search))
        except Exception as err:
            st.error(f"Search failed: {err}")

selected_uri = None
if hits:
    idx = st.radio("Results", options=range(len(hits)), format_func=lambda i: f'{hits[i]["label"]} • {hits[i]["uri"]}')
    selected_uri = hits[idx]["uri"]

manual_uri = st.text_input("Or paste an entity URI directly", value="")
if manual_uri.strip():
    selected_uri = manual_uri.strip()

if selected_uri:
    with st.spinner("Loading entity details..."):
        try:
            data = get_entity(ENDPOINT, selected_uri, lang.strip(), int(limit_rel))
        except Exception as err:
            st.error(f"Failed to load entity: {err}")
        else:
            st.subheader(data["label"])
            if data["comment"]:
                st.write(data["comment"])
            if data["types"]:
                st.markdown("**Types:** " + " ".join(f'`{t["label"]}`' for t in data["types"]))
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### Outgoing")
                if data["outgoing"]:
                    st.dataframe(data["outgoing"], use_container_width=True)
                else:
                    st.caption("No outgoing IRIs within limit.")
            with col2:
                st.markdown("#### Incoming")
                if data["incoming"]:
                    st.dataframe(data["incoming"], use_container_width=True)
                else:
                    st.caption("No incoming IRIs within limit.")
            st.markdown("#### Graph")
            dot = graph_dot(selected_uri, data["label"], data["outgoing"], data["incoming"])
            st.graphviz_chart(dot, use_container_width=True)
