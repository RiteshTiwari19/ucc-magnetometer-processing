import os

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import dash_uploader as du
from dash import dcc, html, Patch, callback_context, no_update
from dash.dependencies import Output, Input
from dash.exceptions import PreventUpdate
from flask import send_from_directory
from flask import session

from api.DatasetService import DatasetService
from auth import AppIDAuthProvider
from components import FileUploadTabs, Sidebar, Settings, Workspaces, Toast, \
    ModalComponent, NotificationProvider
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


@auth.flask.route("/download/<path:path>/")
@auth.check
def download(path):
    """Serve a file from the upload directory."""
    dir = os.path.join(os.path.dirname(os.getcwd()), 'mag-project', 'data',
                       session[AppIDAuthProvider.APPID_USER_NAME], 'exported')

    format = path.split('.')[-1]
    dataset_id = path.split('.')[0]

    dataset = DatasetService.get_dataset_by_id(dataset_id=dataset_id, session_store=session)
    data_path = dataset.tags['export'][format]

    if len(data_path.split('\\')) > 1:
        dir = os.path.join(dir, data_path.split('\\')[0])
        data_path = data_path.split('\\')[-1]

    return send_from_directory(dir, data_path, as_attachment=True)


app.layout = dmc.MantineProvider(
    children=dmc.NotificationsProvider(html.Div([
        dcc.Location(id="url"),
        dcc.Interval(id="auth-check-interval", interval=1500000),
        dcc.Interval(
            id='notification-interval-component',
            interval=7 * 1000,
            n_intervals=0
        ),
        dcc.Store(id='local', storage_type='local', data={}),
        html.Div([
            html.Div(id='notify-container-placeholder-div'),
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
    Output("notify-container-placeholder-div", "children", allow_duplicate=True),
    Input("notification-interval-component", "n_intervals"),
    prevent_initial_call=True
)
def send_notification(inp):
    triggered = callback_context.triggered
    if not triggered or not inp:
        raise PreventUpdate

    notification = auth.redis_queue.get_nowait()

    if notification:
        notification = notification.split('__')
        notification_meta = notification[0].split(';')
        notification = NotificationProvider.notify(notification[1], action=notification_meta[1],
                                                   notification_id=notification_meta[0])
        return notification
    else:
        return no_update


@app.callback(
    Output("page-content", "children"),
    Output("local", "data", allow_duplicate=True),
    [Input("url", "pathname")],
    prevent_initial_call=True
)
@auth.check
def render_page_content(pathname):
    patch = Patch()
    patch[AppIDAuthProvider.APPID_USER_NAME] = session[AppIDAuthProvider.APPID_USER_NAME]
    patch[AppIDAuthProvider.APPID_USER_EMAIL] = session[AppIDAuthProvider.APPID_USER_EMAIL]
    patch[AppIDAuthProvider.APPID_USER_TOKEN] = session[AppIDAuthProvider.APPID_USER_TOKEN]
    patch[AppIDAuthProvider.APPID_USER_BACKEND_ID] = session[AppIDAuthProvider.APPID_USER_BACKEND_ID]
    patch[AppIDAuthProvider.APPID_USER_ROLES] = session[AppIDAuthProvider.APPID_USER_ROLES]
    patch[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT] = session[
        AppIDAuthProvider.CURRENT_ACTIVE_PROJECT] if AppIDAuthProvider.CURRENT_ACTIVE_PROJECT in session else None
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
