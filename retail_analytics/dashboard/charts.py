from __future__ import annotations

import pandas as pd
import plotly.express as px


PALETTE = ["#417F73", "#D58D4F", "#6F8FB8", "#AA737C", "#A6A176", "#856FA5"]


def make_trend_chart(
    frame: pd.DataFrame,
    value: str,
    forecast: pd.DataFrame | None = None,
    height: int = 285,
):
    if frame.empty:
        return None
    figure = px.line(
        frame,
        x="period",
        y=value,
        color="series",
        markers=True,
        color_discrete_sequence=PALETTE,
    )
    figure.update_traces(line={"width": 3}, marker={"size": 6})
    figure.update_layout(
        height=height,
        margin={"l": 4, "r": 4, "t": 10, "b": 4},
        legend_title_text="",
        hovermode="x unified",
        xaxis_title="",
        yaxis_title="",
        font={"size": 16},
    )
    figure.update_yaxes(tickprefix="$", separatethousands=True, gridcolor="rgba(128,128,128,.18)")
    if forecast is not None and not forecast.empty:
        series_colors = {trace.name: trace.line.color for trace in figure.data}
        for series_name, future in forecast.groupby("series", sort=False):
            actual = frame[frame["series"] == series_name].sort_values("period")
            if actual.empty:
                continue
            future = future.sort_values("period")
            last_actual = actual.iloc[-1]
            color = series_colors.get(series_name, PALETTE[0])
            label = "Holt trend forecast" if series_name == "Overall" else f"{series_name} forecast"
            figure.add_scatter(
                x=[last_actual["period"], *future["period"].tolist()],
                y=[last_actual[value], *future["value"].tolist()],
                mode="lines+markers",
                name=label,
                line={"color": color, "dash": "dash", "width": 2.6},
                marker={"symbol": "diamond", "size": 7},
                hovertemplate="%{x|%b %Y}<br>Forecast: $%{y:,.0f}<extra></extra>",
            )
    return figure


def make_donut_chart(
    frame: pd.DataFrame,
    label: str,
    value: str,
    *,
    show_legend: bool,
    show_labels: bool,
    height: int = 280,
):
    if frame.empty:
        return None
    figure = px.pie(
        frame,
        names=label,
        values=value,
        hole=0.46,
        color_discrete_sequence=PALETTE,
    )
    figure.update_traces(
        textinfo="label+percent" if show_labels else "percent",
        textposition="inside",
        insidetextorientation="horizontal",
        texttemplate="%{percent:.1%}",
        # Leave color unset so Plotly chooses contrasting black/white text per slice.
        textfont={"size": 16, "family": "sans-serif", "weight": 700},
        sort=False,
    )
    if show_legend:
        # Reserve the same drawing area for both bottom pies so their diameters match.
        figure.update_traces(domain={"x": [0.0, 0.70], "y": [0.03, 0.97]})
    figure.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 4, "b": 4},
        showlegend=show_legend,
        clickmode="event+select",
        legend={"font": {"size": 15}, "x": 0.70, "y": 0.5, "xanchor": "left", "yanchor": "middle"},
        font={"size": 15},
    )
    return figure
