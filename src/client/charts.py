"""Build Plotly figures from values supplied by the server API."""
import plotly.graph_objects as go


def line_chart(values, color, background, market=False, period='1W'):
    """Create a line figure without mutating the supplied data."""
    figure = go.Figure(go.Scatter(
        x=list(range(len(values))), y=values, mode='lines',
        line=dict(color=color, width=2 if market else 1.3),
        hovertemplate='$%{y:,.2f}<extra></extra>',
    ))
    if market:
        figure.add_trace(go.Scatter(
            x=[len(values) - 1], y=[values[-1]], mode='markers',
            marker=dict(color=color, size=7), hoverinfo='skip',
        ))
    figure.update_layout(
        template=None, paper_bgcolor=background, plot_bgcolor=background,
        showlegend=False, margin=dict(l=42 if market else 12, r=18, t=20, b=22),
        font=dict(family='Inter, Arial, sans-serif', size=9, color='#7e8897'),
        hovermode='x unified', dragmode=False,
        xaxis=dict(showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(showgrid=market, gridcolor='#1c2330', zeroline=False,
                   fixedrange=True, visible=market, tickprefix='$'),
    )
    if market:
        labels = {
            '1D': ['09:00', '11:00', '13:00', '15:00', '17:00'],
            '1W': ['MON', 'TUE', 'WED', 'THU', 'FRI'],
            '1M': ['WEEK 1', 'WEEK 2', 'WEEK 3', 'WEEK 4', 'WEEK 5'],
            '1Y': ['JAN', 'APR', 'JUL', 'OCT', 'DEC'],
        }
        figure.update_xaxes(tickvals=[0, 1.5, 3, 4.5, 6], ticktext=labels[period], range=[-.2, 6.8])
        # The reference places the price line in the upper half of the chart.
        figure.update_yaxes(range=[0, max(values) * 1.06], tickformat=',.0f',
                            tickvals=[stock_level * max(values) / 360 for stock_level in [200, 240, 280, 320, 360]])
    else:
        figure.update_xaxes(visible=False)
        figure.update_yaxes(range=[0, max(values) * 1.1])
    return figure


def stock_chart(stock, period):
    """Create the selected stock's chart from its API-provided history."""
    return line_chart(stock['history'][period], '#00d391', '#11151d', True, period)


def integrity_chart():
    """Create the static landing-page engine integrity illustration."""
    return line_chart([65, 72, 68, 85, 59, 64], '#bd9600', '#181e29')
