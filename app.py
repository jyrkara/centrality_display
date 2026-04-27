import pandas as pd
import os
from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px

#------------------------
# Standardize section names across years
import re

def standardize_index_names(df, index_column='index'):
    """
    Standardize index names in directed_centralities_df so that pre-1994 and post-1994
    section references have consistent names.
    
    Pre-1994 format: 'title-26_section-1'
    Post-1994 format: 'title-26_part-A_chapter-1_part-I_section-1'
    
    Both will be standardized to: 'title-26_section-1'
    
    Names without a section component (e.g., 'title-26_part-A_chapter-1_part-I')
    or with subsections (e.g., 'title-26_section-1_subsection-a') remain unchanged.
    
    Args:
        df: DataFrame with an index column containing node names
        index_column: Name of the column containing index names (default: 'index')
    
    Returns:
        DataFrame with standardized index names
    """
    df = df.copy()
    
    def standardize_name(name):
        """
        Standardize a single index name.
        
        Rules:
        1. If name contains '_section-' but NOT '_subsection-', extract and standardize
        2. Otherwise, keep the name as-is
        """
        if pd.isna(name):
            return name
        
        # Check if this has a section (but not a subsection)
        if '_section-' in name and '_subsection-' not in name:
            # Extract the title and section number
            # Pattern: Match 'title-XX' and 'section-YYY' (where YYY can be digits and letters)
            title_match = re.match(r'^(title-\d+)', name)
            section_match = re.search(r'_section-([^_]+)$', name)
            
            if title_match and section_match:
                title = title_match.group(1)
                section = section_match.group(1)
                return f"{title}_section-{section}"
        
        # Keep all other names unchanged (subsections, parts without sections, etc.)
        return name
    
    df[index_column] = df[index_column].apply(standardize_name)
    
    return df
# -----------------------------
# Load data
readability_metrics_df = pd.read_csv('output/readability_metrics_1934-2024.csv', low_memory=False)
readability_metrics_df['year'] = readability_metrics_df['year'].apply(lambda x: str(x))
directed_centralities_df = pd.read_csv('output/directed_centralities_1934-2025.csv')


# Apply standardization to directed_centralities_df
directed_centralities_df = standardize_index_names(directed_centralities_df)

readability_metrics_df = standardize_index_names(readability_metrics_df, index_column='id')

directed_metrics_df = readability_metrics_df.merge(
    directed_centralities_df,
    left_on=['id', 'year'],
    right_on=['index', 'year'],
    how='outer'
)
directed_metrics_df = directed_metrics_df.drop(columns='index')
directed_metrics_df = directed_metrics_df[directed_metrics_df['year'] != '2025']
 

# -----------------------------
# Define metrics
 

titles = {
     'id':'id',
    'year':'year',
    'flesch_kincaid': 'Flesch-Kincaid Readability',
    'gunning_fog': 'Gunning Fog Index',
    'smog_index': 'SMOG Readability Index',
    'dale_chall': 'Dale-Chall Readability',
    'word_count': 'Word Count',
    'degree': 'Degree Centrality',
    'eigenvector': 'Eigenvector Centrality',
    'betweenness': 'Betweenness Centrality',
    'closeness': 'Closeness Centrality',
    'pagerank': 'Pagerank Centrality',
    'harmonic': 'Harmonic Centrality'
}
directed_metrics_df.columns = directed_metrics_df.columns.map(titles)
 
# -----------------------------
# Reshape data for easier plotting
melted_df = directed_metrics_df.melt(
    id_vars=['id', 'year'],
    value_vars=list(titles.values()),
    var_name='metric',
    value_name='value'
)

# -----------------------------
# Dash App Setup
app = Dash(__name__)
app.title = "Metric Time Series Dashboard"

# Expose server for production deployment (required by gunicorn)
server = app.server

app.layout = html.Div([
    html.H2("Time Series of All Metrics Across Years for Selected Index"),

    html.Div([
        html.Div([
            html.Label("Select Index (Dropdown):"),
            dcc.Dropdown(
                id="id-dropdown",
                options=[{"label": str(i), "value": i} for i in sorted(melted_df['id'].unique())],
                value=sorted(melted_df['id'].unique())[0],
                clearable=False,
                searchable=False  # Disable typing to prevent freezing with large dataset
            ),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px"}),

        html.Div([
            html.Label("Or Search by Index:"),
            html.Div([
                dcc.Input(
                    id="search-input",
                    type="text",
                    placeholder="e.g., title-26_section-1",
                    debounce=True,  # Only trigger on Enter or blur
                    style={"width": "70%", "marginRight": "10px"}
                ),
                html.Button("Search", id="search-button", n_clicks=0),
            ]),
            html.Div(id="search-feedback", style={"color": "red", "fontSize": "12px", "marginTop": "5px"}),
        ], style={"width": "48%", "display": "inline-block", "padding": "10px", "verticalAlign": "top"}),
    ]),

    html.Div([
        html.Label("Filter Years:"),
        dcc.RadioItems(
            id="year-filter",
            options=[
                {"label": "All Years", "value": "all"},
                {"label": "Only Supplement Years", "value": "supplement"},
                {"label": "Exclude Supplement Years", "value": "no_supplement"}
            ],
            value="all",
            inline=True,
            style={"marginTop": "5px"}
        ),
    ], style={"padding": "10px", "borderTop": "1px solid #ddd", "marginTop": "10px"}),

    dcc.Graph(id="id-timeseries"),
], style={"width": "90%", "margin": "auto"})


# -----------------------------
# Callback to handle search button and Enter key
@app.callback(
    [Output("id-dropdown", "value"),
     Output("search-feedback", "children")],
    [Input("search-button", "n_clicks"),
     Input("search-input", "n_submit")],  # Triggers when Enter is pressed
    State("search-input", "value")
)
def search_index(n_clicks, n_submit, search_text):
    # Don't trigger on initial page load
    if (n_clicks == 0 and n_submit is None) or not search_text:
        return sorted(melted_df['id'].unique())[0], ""

    # Clean up the search text
    search_text = search_text.strip()

    # Check if exact match exists
    if search_text in melted_df['id'].values:
        return search_text, ""

    # Try to find partial matches
    matches = [id_val for id_val in melted_df['id'].unique() if search_text.lower() in str(id_val).lower()]

    if len(matches) == 1:
        return matches[0], f"Found: {matches[0]}"
    elif len(matches) > 1:
        return matches[0], f"Multiple matches found ({len(matches)}). Showing first: {matches[0]}"
    else:
        # No matches found - don't change selection
        return sorted(melted_df['id'].unique())[0], f"No matches found for '{search_text}'"


# -----------------------------
# Callback to update graph based on selected ID and year filter
@app.callback(
    Output("id-timeseries", "figure"),
    [Input("id-dropdown", "value"),
     Input("year-filter", "value")]
)
def update_graph(selected_id, year_filter):
    # Handle invalid or None selections
    if selected_id is None or selected_id not in melted_df['id'].values:
        # Return empty figure if selection is invalid
        fig = px.line(title="Please select a valid index")
        return fig

    # Filter by selected ID
    df = melted_df[melted_df['id'] == selected_id].copy()

    # Apply year filter
    if year_filter == "supplement":
        # Only keep years with "supplement" in the name
        df = df[df['year'].str.contains('supplement', case=False, na=False)]
        filter_label = " (Supplement Years Only)"
    elif year_filter == "no_supplement":
        # Exclude years with "supplement" in the name
        df = df[~df['year'].str.contains('supplement', case=False, na=False)]
        filter_label = " (Excluding Supplement Years)"
    else:
        filter_label = ""

    # Check if any data remains after filtering
    if df.empty:
        fig = px.line(title=f"No data available for ID {selected_id} with current filter")
        return fig

    # Line plot of all metrics vs year
    fig = px.line(
        df,
        x="year",
        y="value",
        color="metric",
        markers=True,
        title=f"All Metrics Across Years — ID {selected_id}{filter_label}"
    )

    fig.update_layout(
        width=1400,
        height=800,
        legend_title_text="Metric",
        xaxis_title="Year",
        yaxis_title="Metric Value",
    )

    return fig


# -----------------------------
if __name__ == "__main__":
    # Get port from environment variable (used by Render/Heroku)
    port = int(os.environ.get("PORT", 8050))

    # Check if running in production
    debug_mode = os.environ.get("DEBUG", "False").lower() == "true"

    app.run(host="0.0.0.0", port=port, debug=debug_mode)
