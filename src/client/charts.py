import plotly.graph_objects as go
from datetime import datetime


def line_chart(values, color, background, market=False, times=None, window=None):
    if market:
        x_values = times
        line_width = 2
        hover_text = '%{x|%H:%M:%S}<br>$%{y:,.2f}<extra></extra>'
        left_margin = 42
    else:
        x_values = list(range(len(values)))
        line_width = 1.3
        hover_text = '$%{y:,.2f}<extra></extra>'
        left_margin = 12
    figure = go.Figure(go.Scatter(
        x=x_values, y=values, mode='lines',
        line=dict(color=color, width=line_width),
        hovertemplate=hover_text,
    ))
    if market:
        figure.add_trace(go.Scatter(
            x=[times[-1]], y=[values[-1]], mode='markers',
            marker=dict(color=color, size=7), hoverinfo='skip',
        ))
    figure.update_layout(
        template=None, paper_bgcolor=background, plot_bgcolor=background,
        showlegend=False, margin=dict(l=left_margin, r=18, t=20, b=22),
        font=dict(family='Inter, Arial, sans-serif', size=9, color='#7e8897'),
        hovermode='x unified', dragmode=False,
        xaxis=dict(showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(showgrid=market, gridcolor='#1c2330', zeroline=False,
                   fixedrange=True, visible=market, tickprefix='$'),
    )
    if market:
        padding = max((max(values) - min(values)) * 0.15, max(values) * 0.002)
        figure.update_xaxes(
            title='LOCAL TIME', type='date', range=window,
            tickformat='%H:%M', dtick=60_000,
        )
        figure.update_yaxes(range=[max(0, min(values) - padding), max(values) + padding])
    else:
        figure.update_xaxes(visible=False)
        figure.update_yaxes(range=[0, max(values) * 1.1])
    return figure


def stock_chart(stock, period):
    times = []
    for value in stock['history_times']:
        times.append(datetime.fromtimestamp(value).isoformat())
    window = [
        datetime.fromtimestamp(stock['chart_start']).isoformat(),
        datetime.fromtimestamp(stock['chart_end']).isoformat(),
    ]
    return line_chart(
        stock['history'][period], '#00d391', '#11151d',
        market=True, times=times, window=window,
    )


def integrity_chart():
    return line_chart([65, 72, 68, 85, 59, 64], '#bd9600', '#181e29')
