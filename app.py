import json
import time
import requests
import pandas as pd
import streamlit as st

# --- Theming / styling ---
st.set_page_config(page_title="Bekhabar – FIFA Linked Data Explorer", page_icon="⚽", layout="wide")
st.markdown(
    """
    <style>
        :root {
            --primary-color: #0b3d0b;
            --accent-gold: #d4af37;
            --text-light: #f8f8f8;
        }
        body, .stApp { background-color: #0a2f0a; color: var(--text-light); }
        .css-18ni7ap, .stMarkdown, .stTextInput, .stTextArea, .stSelectbox, .stButton button {
            color: var(--text-light);
        }
        .stButton button {
            background-color: var(--accent-gold);
            color: #0b3d0b;
            border-radius: 8px;
            border: none;
            font-weight: 700;
        }
        .stTextArea textarea {
            background-color: #0f4d0f;
            color: var(--text-light);
        }
        h1, h2, h3 { color: var(--accent-gold); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Bekhabar – FIFA Linked Data Explorer ⚽")
st.subheader("Query FIFA data using SPARQL")

# --- Sidebar configuration ---
st.sidebar.header("SPARQL Endpoint")
default_endpoint = "https://example.org/sparql"
endpoint_url = st.sidebar.text_input("Endpoint URL", value=default_endpoint)

# Example queries with autofill
example_queries = {
    "Players by nationality": """
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX dbr: <http://dbpedia.org/resource/>
SELECT ?player ?club
WHERE {
  ?player dbo:position dbr:Association_football_forward ;
          dbo:nationality dbr:Brazil ;
          dbo:currentclub ?club .
}
LIMIT 20
""",
    "Clubs by league": """
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX dbr: <http://dbpedia.org/resource/>
SELECT ?club ?stadium
WHERE {
  ?club dbo:league dbr:Premier_League ;
        dbo:ground ?stadium .
}
LIMIT 20
""",
    "Stadiums capacity": """
PREFIX dbo: <http://dbpedia.org/ontology/>
SELECT ?stadium ?capacity
WHERE {
  ?stadium a dbo:Stadium ;
           dbo:capacity ?capacity .
}
ORDER BY DESC(?capacity)
LIMIT 20
""",
}

st.sidebar.markdown("**Example Queries**")
if "query_text" not in st.session_state:
    st.session_state["query_text"] = list(example_queries.values())[0]

for label, query in example_queries.items():
    if st.sidebar.button(label):
        st.session_state["query_text"] = query

# --- Main layout ---
st.markdown("Write a SPARQL query and hit **Run Query** to explore FIFA-linked data.")
query_text = st.text_area("SPARQL Query", height=280, value=st.session_state["query_text"], key="query_text_area")
run_clicked = st.button("Run Query")

# --- Helper: execute SPARQL ---
def execute_sparql(query: str, endpoint: str) -> pd.DataFrame:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    params = {"query": query}
    try:
        resp = requests.post(endpoint, data=params, headers=headers, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"Connection error: {exc}") from exc

    if resp.status_code >= 400:
        raise RuntimeError(f"Endpoint returned {resp.status_code}: {resp.text}")

    try:
        payload = resp.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response: {exc}") from exc

    vars_list = payload.get("head", {}).get("vars", [])
    bindings = payload.get("results", {}).get("bindings", [])
    if not bindings:
        return pd.DataFrame(columns=vars_list)

    rows = []
    for b in bindings:
        row = {var: b.get(var, {}).get("value") for var in vars_list}
        rows.append(row)
    return pd.DataFrame(rows, columns=vars_list)

# --- Run query and render ---
if run_clicked:
    if not query_text.strip():
        st.error("Please enter a SPARQL query before running.")
    elif not endpoint_url.strip():
        st.error("Please provide a SPARQL endpoint URL.")
    else:
        start = time.perf_counter()
        try:
            df = execute_sparql(query_text, endpoint_url.strip())
            elapsed = time.perf_counter() - start
            if df.empty:
                st.info("No results found.")
            else:
                st.dataframe(df, use_container_width=True)
            st.caption(f"Execution time: {elapsed:.2f}s via POST")
        except RuntimeError as err:
            st.error(f"Query failed: {err}")
        except Exception as err:
            st.error(f"Unexpected error: {err}")
