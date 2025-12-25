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
ENDPOINT = "https://genotypical-mao-coxal.ngrok-free.dev/repositories/new-fifa"
st.sidebar.caption(f"Endpoint: `{ENDPOINT}` (fixed)")

# Example queries with autofill
example_queries = {
    "High-Pace Left-Footed Outfielders": """
PREFIX fifa: <http://example.org/fifa/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?player ?name ?pace ?dribbling 
WHERE { 
    ?player a fifa:OutfieldPlayer ; 
            fifa:name ?name ; 
            fifa:hasPreferredFoot fifa:LeftFoot ; 
            fifa:hasSkill fifa:pace ; 
            fifa:hasSkill fifa:dribbling . 
            
    fifa:pace fifa:skillValue ?pace . 
    fifa:dribbling fifa:skillValue ?dribbling . 
    
    FILTER (?pace > 85 && ?dribbling > 85) 
} 
ORDER BY DESC(?pace)
""",
    "Top Rated Players (Overall > 85)": """
PREFIX fifa: <http://example.org/fifa/> 
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?player ?name ?rating
WHERE {
    ?player a fifa:Player ;
            fifa:name ?name ;    
            fifa:overallRating ?rating .
    FILTER (?rating > 85)
}
ORDER BY DESC(?rating)
""",
    "Clubs with Diverse Nationalities (More than 5)": """
PREFIX fifa: <http://example.org/fifa/> 
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?club (COUNT(DISTINCT ?country) AS ?nationalityCount)
WHERE {
    ?player fifa:playsFor ?club ;
            fifa:representsNation ?country .
}
GROUP BY ?club
HAVING (COUNT(DISTINCT ?country) > 5)
ORDER BY DESC(?nationalityCount)
""",
    "Versatile Players with Elite Skills (Multiple Positions & Skill >= 85)": """
PREFIX fifa: <http://example.org/fifa/> 
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?player ?name (COUNT(DISTINCT ?pos) AS ?positionCount) 
WHERE {
    ?player a fifa:Player ;
            fifa:name ?name ;
            fifa:hasPosition ?pos ;
            fifa:hasSkill ?skill .
    
    ?skill fifa:skillValue ?value .
    
    FILTER (?value >= 85)
}
GROUP BY ?player ?name
HAVING (COUNT(DISTINCT ?pos) > 1)
ORDER BY DESC(?positionCount)
""",
    "Elite Performance Clubs (Average Rating > 80)": """
PREFIX fifa: <http://example.org/fifa/> 
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?club (AVG(?rating) AS ?avgRating) 
WHERE {
    ?player fifa:playsFor ?club ;
            fifa:overallRating ?rating .
}
GROUP BY ?club
HAVING (AVG(?rating) > 80)
ORDER BY DESC(?avgRating)
""",
    "Expatriate Players (Club and Country Name Mismatch)": """
PREFIX fifa: <http://example.org/fifa/>

SELECT ?player ?name ?club ?country 
WHERE {
    ?player a fifa:Player ;
            fifa:name ?name ;
            fifa:playsFor ?club ;
            fifa:representsNation ?country .

    FILTER (!STRENDS(STR(?club), STR(?country)))
}
""",
    "Top Tier Goalkeeper Reflexes": """
PREFIX fifa: <http://example.org/fifa/>

SELECT ?player ?name ?reflexes
WHERE {
    ?player a fifa:Goalkeeper ;
            fifa:name ?name ;
            fifa:hasSkill ?reflexSkill .
            
    ?reflexSkill a fifa:Skill ;
                 fifa:skillValue ?reflexes .
                 
    FILTER(CONTAINS(STR(?reflexSkill), "goalkeeping_reflexes"))
    FILTER(?reflexes > 85)
}
ORDER BY DESC(?reflexes)
""",
    "Expiring Contracts (End of 2025 or earlier)": """
PREFIX fifa: <http://example.org/fifa/> 
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?player ?name ?contractYear
WHERE {
    ?player fifa:name ?name ;
            fifa:contractUntil ?contractYear .
            
    FILTER(xsd:integer(STR(?contractYear)) <= 2025)
}
ORDER BY ?contractYear
""",
    "Club Counts for High-Reputation Players (Reputation >= 4)": """
PREFIX fifa: <http://example.org/fifa/> 
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT ?club (COUNT(?player) AS ?playerCount)
WHERE {
    ?player fifa:hasSkill ?repSkill ;
            fifa:playsFor ?club .
            
    ?repSkill a fifa:Skill ;
              fifa:skillValue ?repValue .
              
    FILTER(?repValue >= 4)
}
GROUP BY ?club
ORDER BY DESC(?playerCount)
"""
}

st.sidebar.markdown("**Example Queries**")
if "query_text" not in st.session_state:
    st.session_state["query_text"] = list(example_queries.values())[0]
if "query_text_area" not in st.session_state:
    st.session_state["query_text_area"] = st.session_state["query_text"]

for label, query in example_queries.items():
    if st.sidebar.button(label):
        st.session_state["query_text"] = query
        st.session_state["query_text_area"] = query

# --- Main layout ---
st.markdown("Write a SPARQL query and hit **Run Query** to explore FIFA-linked data.")
query_text = st.text_area(
    "SPARQL Query",
    height=280,
    value=st.session_state["query_text_area"],
    key="query_text_area",
)
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
    else:
        start = time.perf_counter()
        try:
            df = execute_sparql(query_text, ENDPOINT)
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
