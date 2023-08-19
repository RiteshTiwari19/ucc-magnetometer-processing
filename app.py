import os

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import dash_uploader as du
from dash import dcc, html, Patch
from dash.dependencies import Output, Input
from flask import session

from auth import AppIDAuthProvider
from components import FileUploadTabs, Sidebar, Settings, Workspaces, MagDataComponent, Toast, ModalComponent
from dataservices import InMermoryDataService

DASH_URL_BASE_PATHNAME = "/dashboard/"

auth = AppIDAuthProvider(DASH_URL_BASE_PATHNAME)
app = dash.Dash(__name__,
                server=auth.flask,
                url_base_pathname=DASH_URL_BASE_PATHNAME,
                external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
                suppress_callback_exceptions=True)

du.configure_upload(app, os.getcwd() + "\\data")

# the styles for the main content position it to the right of the sidebar and add some padding.
CONTENT_STYLE = {
    # "padding": "1rem 1rem",
    "margin": "1rem",
    "width": "95%",
}

app.layout = dmc.MantineProvider(
    children=dmc.NotificationsProvider(html.Div([
        dcc.Location(id="url"),
        dcc.Interval(id="auth-check-interval", interval=1500000),
        dcc.Interval(id="notification-checker", interval=1*1000, n_intervals=0),
        dcc.Store(id='local', storage_type='local', data={}),
        html.Div([
            html.Div(id='toast-placeholder-div'),
            html.Div([Sidebar.sidebar], style={'maxWidth': '20%', 'minWidth': '12%'}, id='sidebar_parent_div'),
            html.Div(html.Div(id="page-content", style=CONTENT_STYLE),
                     style={'width': '100%', 'marginLeft': '1rem',
                            'overflow': 'scroll'
                            }),
        ], style={'justifyContent': 'flex-start',
                  'position': 'relative',
                  'display': 'flex',
                  'flexDirection': 'row',
                  'flex': 'auto',
                  'height': '100%',
                  'alignItems': 'stretch',
                  'alignSelf': 'stretch',
                  }, id='app_layout_div'),

    ], style={'margin': 0, 'display': 'flex', 'flexDirection': 'column'})),
    theme={"colorScheme": "dark",
           "colors":
               {"wine-red": ["#C85252"] * 9}
           }
)

Sidebar.hover(app)


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
@auth.check
def render_page_content(pathname):
    if pathname == "/dashboard/":
        return Workspaces.get_workspaces_html(len(InMermoryDataService.WorkspaceService.workspaces))
    elif pathname == "/dashboard/datasets":
        return FileUploadTabs.datasets_tabs
    elif pathname == "/dashboard/explore":
        return html.P("Oh cool, this is page 2!")
    elif pathname == "/dashboard/settings":
        return Settings.get_settings_page(session)
    # If the user tries to reach a different page, return a 404 message
    return html.Div(
        [
            html.H1("404: Not found", className="text-danger"),
            html.Hr(),
            html.P(f"The pathname {pathname} was not recognised..."),
        ],
        className="p-3 bg-dark rounded-3",
    )


@du.callback(
    output=[Output("local", "data", allow_duplicate=True),
            Output("toast-placeholder-div", "children", allow_duplicate=True)],
    id="uploader",
)
def callback_on_upload_completion(status: du.UploadStatus):
    patch_object = Patch()
    session[AppIDAuthProvider.LAST_DATASET_UPLOADED] = status.latest_file.as_uri()
    patch_object[AppIDAuthProvider.LAST_DATASET_UPLOADED] = status.latest_file.as_uri()
    return patch_object, Toast.get_toast("Notification", 'File Uploaded Successfully')


Sidebar.sidebar_user(app)

FileUploadTabs.switch_dataset_tab(app, du)

Workspaces.switch_workspace_tab_outer(app, du)

Workspaces.workspace_button_handler(app)

ModalComponent.toggle_upload_dataset_modal(app)

Toast.open_toast(app)

MagDataComponent.hide_dataset_selection_div_outer(app)

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", debug=True)
