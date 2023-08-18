import dash
import dash_bootstrap_components as dbc

from components import DashUploader, FileUploadTabs
from dash import html, Input, Output, State, ALL
import dash_mantine_components as dmc


def get_upload_data_modal(configured_du, upload_id):
    modal = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Upload New Dataset")),
            dbc.ModalBody([
                FileUploadTabs.get_upload_file_tab_content(configured_du, upload_id=upload_id),

            ]),
            dbc.ModalFooter(
                dbc.Button(
                    "Close", id={'type': 'button', 'subset': 'modal', 'action': 'close', 'idx': 'close-upload-modal'},
                    className="ms-auto", n_clicks=0
                )
            ),
        ],
        id="upload-page-modal",
        is_open=False,
        size='xl',
        scrollable=True,
        zIndex=3,
        zindex=3
    ),

    return modal


def toggle_upload_dataset_modal(app: dash.Dash):
    @app.callback(
        Output("upload-page-modal", "is_open"),
        [Input({'type': 'button', 'subset': 'modal', 'action': ALL, 'idx': 'open-upload-modal'}, "n_clicks"),
         Input({'type': 'button', 'subset': 'modal', 'action': ALL, 'idx': 'close-upload-modal'}, "n_clicks")],
        [State("upload-page-modal", "is_open")],
        prevent_initial_call=True
    )
    def toggle_upload_dataset_modal(n1, n2, is_open):
        if n1 or n2:
            return not is_open
        return is_open
