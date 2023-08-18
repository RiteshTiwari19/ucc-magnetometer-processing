from dash import html

from auth import AppIDAuthProvider


def get_settings_page(session):
    settings_page = html.Div([
        html.Div([
            "Settings"
        ], className="card-header"),
        html.Div([
            html.H4("User Information", className="card-title"),
            html.Br(),
            html.Br(),
            html.P(f"Username: {session[AppIDAuthProvider.APPID_USER_NAME]}", className="card-text"),
            html.P(f"Email: {session[AppIDAuthProvider.APPID_USER_EMAIL]}")
        ], className="card-body"),
    ], className="card text-white card border-none mb-3")

    return settings_page


