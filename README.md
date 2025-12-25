# bekhabar
Bekhabar is a lightweight web interface for exploring FIFA-related linked data using SPARQL.

## Running
```bash
streamlit run app.py
```
The app is multi-page:
- **Home:** run arbitrary SPARQL queries and view tabular results.
- **Linked Data Explorer (pages/linked_data_explorer.py):** search by label, open entity detail, browse incoming/outgoing relations, and view a small graph without writing SPARQL.
