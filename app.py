import pandas as pd
import os
from dash import Dash, dcc, html, Input, Output
import plotly.express as px

# -----------------------------
# Load data
readability_metrics_df = pd.read_csv('output/readability_metrics_1934-2024.csv', low_memory=False)
readability_metrics_df['year'] = readability_metrics_df['year'].apply(lambda x: str(x))
directed_centralities_df = pd.read_csv('output/directed_centralities_1934-2025.csv')

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
metrics = [
    'flesch_kincaid', 'gunning_fog', 'smog_index', 'dale_chall',
    'word_count', 'degree', 'eigenvector', 'betweenness', 'closeness',
    'subgraph', 'pagerank', 'harmonic',
]

titles = {
    'flesch_kincaid': 'Flesch-Kincaid Readability',
    'gunning_fog': 'Gunning Fog Index',
    'smog_index': 'SMOG Readability Index',
    'dale_chall': 'Dale-Chall Readability',
    'word_count': 'Word Count',
    'degree': 'Degree Centrality',
    'eigenvector': 'Eigenvector Centrality',
    'betweenness': 'Betweenness Centrality',
    'closeness': 'Closeness Centrality',
    'subgraph': 'Subgraph Centrality',
    'pagerank': 'Pagerank Centrality',
    'harmonic': 'Harmonic Centrality'
}

# -----------------------------
# Reshape data for easier plotting
melted_df = directed_metrics_df.melt(
    id_vars=['id', 'year'],
    value_vars=metrics,
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
        html.Label("Select Index:"),
        dcc.Dropdown(
            id="id-dropdown",
            options=[{"label": str(i), "value": i} for i in sorted(melted_df['id'].unique())],
            value=sorted(melted_df['id'].unique())[0],
            clearable=False
        ),
    ], style={"width": "50%", "padding": "10px"}),

    dcc.Graph(id="id-timeseries"),
], style={"width": "90%", "margin": "auto"})


# -----------------------------
# Callback to update graph based on selected ID
@app.callback(
    Output("id-timeseries", "figure"),
    Input("id-dropdown", "value")
)
def update_graph(selected_id):
    df = melted_df[melted_df['id'] == selected_id]

    # Line plot of all metrics vs year
    fig = px.line(
        df,
        x="year",
        y="value",
        color="metric",
        markers=True,
        title=f"All Metrics Across Years — ID {selected_id}"
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
