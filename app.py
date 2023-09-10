import os

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import dash_uploader as du
from dash import dcc, html, Patch
from dash.dependencies import Output, Input
from flask import session
from flask import Flask, send_from_directory

from auth import AppIDAuthProvider
from components import FileUploadTabs, DatasetsComponent, Sidebar, Settings, Workspaces, ResidualComponent, Toast, \
    ModalComponent
from dataservices import InMermoryDataService
from utils.ExportUtils import ExportUtils

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


@auth.flask.route("/download/<path:path>/")
@auth.check
def download(path):
    """Serve a file from the upload directory."""
    root_dir = os.path.dirname(os.getcwd())
    dir = os.path.join(root_dir, 'mag-project', 'data', 'Ritesh Tiwari', 'processed')

    azr_path = path.split('____')[-1]
    path = path.split('____')[0]

    if not os.path.exists(f"{dir}/{path}"):
        if path.endswith('csv'):
            ExportUtils.export_csv(dataset_path=azr_path, dataset_id=None, session=session)
        elif path.endswith('zip'):
            dir_out, path = ExportUtils.export_shp_file(dataset_path=azr_path, session=session, dataset_id=None)
            dir = dir + dir_out

    return send_from_directory(dir, path, as_attachment=True)


app.layout = dmc.MantineProvider(
    children=dmc.NotificationsProvider(html.Div([
        dcc.Location(id="url"),
        dcc.Interval(id="auth-check-interval", interval=1500000),
        html.Div(id='notify-container-placeholder-div'),
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

    ], style={'margin': 0, 'display': 'flex', 'flexDirection': 'column'}),
        limit=4
    ),
    theme={"colorScheme": "dark",
           "colors":
               {"wine-red": ["#C85252"] * 9,
                "dark-green": ["#009688"] * 9,
                "dark-yellow": ["#5C6BC0"] * 9,
                "dark-gray": ["#212121"] * 9,
                "light-cyan": ["#B2EBF2"] * 9
                }
           }
)

Sidebar.hover(app)


@app.callback(
    Output("page-content", "children"),
    Output("local", "data"),
    [Input("url", "pathname")]
)
@auth.check
def render_page_content(pathname):
    patch = Patch()
    patch[AppIDAuthProvider.APPID_USER_NAME] = session[AppIDAuthProvider.APPID_USER_NAME]
    patch[AppIDAuthProvider.APPID_USER_EMAIL] = session[AppIDAuthProvider.APPID_USER_EMAIL]
    patch[AppIDAuthProvider.APPID_USER_TOKEN] = session[AppIDAuthProvider.APPID_USER_TOKEN]
    patch[AppIDAuthProvider.APPID_USER_BACKEND_ID] = session[AppIDAuthProvider.APPID_USER_BACKEND_ID]
    patch[AppIDAuthProvider.APPID_USER_ROLES] = session[AppIDAuthProvider.APPID_USER_ROLES]
    patch[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT] = session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT] if AppIDAuthProvider.CURRENT_ACTIVE_PROJECT in session else None
    if pathname == "/dashboard/":
        return Workspaces.get_workspaces_html(len(InMermoryDataService.WorkspaceService.workspaces)), patch
    elif pathname == "/dashboard/datasets":
        return FileUploadTabs.datasets_tabs, patch
    elif pathname == "/dashboard/explore":
        return html.P("Oh cool, this is page 2!"), patch
    elif pathname == "/dashboard/settings":
        return Settings.get_settings_page(session), patch
    # If the user tries to reach a different page, return a 404 message
    return html.Div(
        [
            html.H1("404: Not found", className="text-danger"),
            html.Hr(),
            html.P(f"The pathname {pathname} was not recognised..."),
        ],
        className="p-3 bg-dark rounded-3",
    ), patch


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

# FileUploadTabs.switch_dataset_tab(app, du)
FileUploadTabs.switch_datasets_tab_outer(app, du)

Workspaces.switch_workspace_tab_outer(app, du)

ModalComponent.toggle_upload_dataset_modal(app)

Toast.open_toast(app)

if __name__ == "__main__":
    app.run_server(host="0.0.0.0", debug=True)
