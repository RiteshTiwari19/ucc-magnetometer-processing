import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, html


def get_toast(header, text, icon="success"):
    toast = html.Div(
        [
            dbc.Toast(
                text,
                id="notification-toast",
                header=header,
                is_open=True,
                duration=3000,
                dismissable=True,
                icon=icon,
                style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 5},
            ),
        ]
    )

    return toast


def open_toast(app: dash.Dash):
    @app.callback(
        Output("positioned-toast", "is_open"),
        [Input("positioned-toast-toggle", "n_clicks")],
    )
    def open_toast(n):
        if n:
            return True
        return False
