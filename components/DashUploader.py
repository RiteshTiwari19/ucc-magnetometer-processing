import uuid

from dash import html
import dash_bootstrap_components as dbc


def get_upload_component(configured_du, cid="uploader", upload_id=uuid.uuid1()):
    return html.Div([
        configured_du.Upload(
            id=cid,
            text='Drag and Drop files here or Click to upload!',
            max_file_size=4000,  # 4000 Mb,
            max_files=4,
            pause_button=True,
            filetypes=['csv', 'zip', 'txt'],
            default_style={'width': '100%'},
            upload_id=upload_id,  # Unique session id
        )
    ],
        style={
            'textAlign': 'center',
            'width': '100%',
            'padding': '10px',
            'display': 'inline-block'
        }
    )
