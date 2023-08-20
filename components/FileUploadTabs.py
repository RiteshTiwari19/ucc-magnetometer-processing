import glob
import os
import shutil
from zipfile import ZipFile

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
from dash import html, Output, Input, callback, no_update, State, ctx, clientside_callback, Patch, ALL
from dash_iconify import DashIconify
from flask import session

from auth import AppIDAuthProvider
from components import DashUploader, DataTableNative, Toast, DataUploadSummaryPageComponent, NotificationProvider
from dataservices import InMermoryDataService
from utils import Utils
from FlaskCache import background_callback_manager, celery_app

min_step = 0
max_step = 3
active = 0

datasets_tabs = html.Div(
    [
        dbc.Tabs(
            [
                dbc.Tab(label="Existing Datasets", tab_id="existing_datasets", activeTabClassName="fw-bold",
                        activeLabelClassName="text-success"),
                dbc.Tab(label="Upload", tab_id="file_upload", activeTabClassName="fw-bold",
                        activeLabelClassName="text-success"),
            ],
            id="tabs",
            active_tab="existing_datasets",
        ),
        html.Div(id="content", style={'width': '100%'},
                 children=dmc.Stack(
                     spacing="xs",
                     children=[
                         dmc.Skeleton(radius=8, circle=True),
                         dmc.Skeleton(height=40, width="100%", visible=True),
                         dmc.Skeleton(height=40, width="100%", visible=True),
                         dmc.Skeleton(height=40, width="100%", visible=True),
                         dmc.Skeleton(height=40, width="100%", visible=True),
                     ],
                 )
                 ),
    ],
    style={
        'textAlign': 'center',
        'width': '100%',
        'padding': '10px',
        'display': 'inline-block'
    }
)


def get_upload_file_tab_content(configured_du, upload_id):
    content = html.Div([
        dmc.Affix(id='notify-container-placeholder-div', position={"bottom": 30, "right": 30}),
        get_stepper(configured_du, upload_id),
    ],
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'flexWrap': 'wrap',
            'justifyContent': 'center',
            'alignContent': 'center',
            'width': '100%',
            'padding': '1rem',
            'marginTop': '1rem'
        },
    )
    return content


def get_stepper(configured_du, upload_id):
    data_types = InMermoryDataService.DatasetsService.get_dataset_types()
    data_types = [{'label': data_type.name, 'value': data_type.id} for data_type in data_types]

    stepper = html.Div(
        [
            dmc.Stepper(
                id="upload-data-stepper",
                active=0,
                breakpoint="sm",
                children=[
                    dmc.StepperStep(
                        label="Dataset",
                        description="Upload a dataset",
                        children=[
                            html.Br(),
                            dmc.TextInput(
                                id='upload-dataset-name',
                                placeholder='Provide a name for the dataset',
                                radius=5
                            ),
                            html.Br(),
                            dmc.Select(
                                data=data_types,
                                label="Please select a dataset type",
                                id='upload-select-dataset',
                                searchable=True,
                                nothingFound="Invalid Data Type",
                                icon=DashIconify(icon="ep:data-line"),
                                placeholder='Select Dataset Type',
                                persisted_props=['value'],
                                persistence_type='session',
                                required=True,
                                persistence=True,
                                selectOnBlur=True,
                                clearable=True
                            ),
                            html.Br(),
                            html.Div(DashUploader.get_upload_component(configured_du, upload_id=upload_id),
                                     className='hide-div', id='dash_uploader-div')
                        ],
                    ),
                    dmc.StepperStep(
                        label="Select Columns",
                        description="Please select the required columns for the dataset type",
                        children=dmc.Loader(color="red", size="md", variant="oval"),
                        id='select_columns_step'
                    ),
                    dmc.StepperStep(
                        label="Summary and Upload",
                        description="Review and Upload the dataset",
                        id='review-and-finalize-step',
                        children=dmc.Loader(color="red", size="md", variant="oval"),
                    ),
                    dmc.StepperCompleted(
                        children=dmc.Text(
                            "Data upload completed!, click back button to get to previous step",
                            align="center",
                        )
                    ),
                ],
            ),
            dmc.Group(
                position="center",
                mt="xl",
                children=[
                    dmc.Button("Back", id="stepper-back-button", variant="default"),
                    dmc.Button("Next step", id="stepper-next-button"),
                ],
            ),
        ],
        id='upload-data-stepper-configuration', style={'width': '100%'}
    )

    return stepper


@callback(Output("dash_uploader-div", "className"), Input("upload-select-dataset", "value"))
def selected_dataset(value):
    if value:
        return "show-div"
    else:
        return "hide-div"


def read_observatory_data(blob_path):
    ret_df = pd.DataFrame({})
    observatory_files = glob.glob(blob_path)
    for idx, file in enumerate(observatory_files):
        try:
            df = pd.read_table(file, index_col=False)
            ret_df = pd.concat([ret_df, df])
        except:
            print(f'Unable to read file {file}')

    save_location = os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\uploaded_zip.csv"
    ret_df.to_csv(save_location)
    shutil.rmtree(os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\extracted\\")
    return ret_df.reset_index(drop=True)


def get_upload_data_content(data_path=None):
    selected_path = session[AppIDAuthProvider.LAST_DATASET_UPLOADED]
    if data_path:
        if selected_path.endswith('.csv'):
            df = pd.read_csv(session[AppIDAuthProvider.LAST_DATASET_UPLOADED]).dropna().sample(2000)
        else:
            if selected_path.endswith('.zip'):
                data_path_file = selected_path.split('/')[-1]
                data_path = os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\{data_path_file}"
                with ZipFile(data_path, 'r') as z_object:
                    extract_path = os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\extracted"
                    if not os.path.exists(extract_path):
                        os.mkdir(extract_path)

                    try:
                        z_object.extractall(path=f"{extract_path}")
                        df = read_observatory_data(f'{extract_path}\\*.txt').sample(2000)
                        df = df.loc[:, df.columns[:-1]]
                    except Exception as e:
                        print(e)
            else:
                df = pd.read_table(selected_path, index_col=False).sample(8)
        return dmc.LoadingOverlay(
            dmc.Stack([
                dmc.Center(
                    dmc.Text("Data Sample",
                             variant="gradient",
                             gradient={"from": "red", "to": "yellow", "deg": 45},
                             style={"fontSize": 20})),
                html.Div(
                    DataTableNative.get_native_datable(df),
                    id='data-table-container'
                ),
                dmc.Center(
                    dmc.Text("Column Selection",
                             variant="gradient",
                             gradient={"from": "red", "to": "yellow", "deg": 45},
                             style={"fontSize": 20})),

                *get_data_cols(session, df)

            ]
            ),
            loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
            style={'flex': '1 1 0', 'maxWidth': '100%'}
        )
    else:
        return html.Div()


def get_review_and_finalize_content(data_path=None,
                                    data_type='SURVEY_DATA',
                                    session=None):
    if data_path:

        df = pd.read_csv(data_path)

        return dmc.LoadingOverlay(
            dmc.Stack([
                dmc.Center(
                    dmc.Text("Data Statistics",
                             variant="gradient",
                             gradient={"from": "red", "to": "yellow", "deg": 45},
                             style={"fontSize": 20})),
                html.Div(
                    DataUploadSummaryPageComponent.get_upload_summary(data_type,
                                                                      df,
                                                                      session),
                    id='data-table-container'
                )
            ]
            ),
            loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
            style={'flex': '1 1 0', 'maxWidth': '100%'}
        )
    else:
        return html.Div()


def save_and_validate_survey_data(dataset_type_name, data_path, dataset_name, lat_long_switch, latitude, longitude,
                                  easting_northing_switch, easting,
                                  northing, zone, depth_altitude_switch, depth, altitude,
                                  depth_regex, alt_regex, total_field, datetime):
    err_message = []

    col_map = {}

    if not total_field or not datetime:
        err_message += ['Total Magnetic Field and Datetime column must be provided']
    else:
        col_map[datetime] = 'Datetime'
        col_map[total_field] = 'Magnetic_Field'

    if lat_long_switch:
        if not latitude or not longitude:
            err_message += ["Latitude and Longitude must be provided"]
        else:
            col_map[latitude] = 'Latitude'
            col_map[longitude] = 'Longitude'
    if easting_northing_switch:
        if not easting or not northing or not zone:
            err_message += ["Easting, Northing, and Zone must be provided"]
        else:
            col_map[easting] = 'Easting'
            col_map[northing] = 'Northing'
            col_map[zone] = 'Zone'
    if depth_altitude_switch:
        if not depth or not altitude:
            pass
            # err_message += ["Depth and Altitude must be provided"]
        else:
            col_map[depth] = 'Depth'
            col_map[altitude] = 'Altitude'

    if len(err_message) > 0:
        return None, err_message
    else:
        try:
            col_map_keys = list(col_map.keys())
            df = pd.read_csv(data_path)[col_map_keys]
            df = df.rename(columns=col_map)

            df = df[df['Easting'] != '*']
            df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)
            df['Datetime'] = pd.to_datetime(df['Datetime'], format="mixed")

            if latitude in col_map_keys:
                df['Latitude'] = df['Latitude'].astype(float)
            if longitude in col_map_keys:
                df['Longitude'] = df['Longitude'].astype(float)
            if easting in col_map_keys:
                df['Easting'] = df['Easting'].astype(float)
            if northing in col_map_keys:
                df['Northing'] = df['Northing'].astype(float)
            if depth in col_map_keys:
                df['Depth'] = df['Depth'].astype(str).str.extract(depth_regex)
            if altitude in col_map_keys:
                df['Altitude'] = df['Altitude'].astype(str).str.extract(alt_regex)

        except Exception as e:
            err_message += [str(e)]

        if len(err_message) == 0:
            save_path = os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\processed"
            if not os.path.exists(save_path):
                os.mkdir(save_path)

            df.to_csv(f'{save_path}\\{dataset_name}.csv')

            return f'{save_path}\\{dataset_name}.csv', None
        else:
            return None, err_message


def save_and_validate_observatory_data(dataset_type_name,
                                       dataset_name,
                                       data_path,
                                       observatory_data_switch,
                                       total_field, bx, by, bz, datetime, datetime_xyz):
    err_message = []

    col_map = {}

    if observatory_data_switch:
        if not bx or not by or not bz:
            err_message += ['Directional Magnetic Field Components must be provided']
        else:
            col_map[bx] = 'bx'
            col_map[by] = 'by'
            col_map[bz] = 'bz'

        if not datetime_xyz:
            err_message += ['Datetime must be provided']
        else:
            col_map[datetime_xyz] = 'Datetime'
    else:
        if not total_field:
            err_message += ['Total Magnetic Field must be provided']
        else:
            col_map[total_field] = 'Magnetic_Field'

        if not datetime:
            err_message += ['Datetime must be provided']
        else:
            col_map[datetime] = 'Datetime'

    if len(err_message) > 0:
        return None, err_message
    else:
        try:

            col_map_keys = list(col_map.keys())

            df = pd.read_csv(data_path)[col_map_keys] if data_path.endswith('csv') else \
                pd.read_table(data_path, index_col=False)[col_map_keys]
            df = df.rename(columns=col_map)

            df['Datetime'] = pd.to_datetime(df['Datetime'], format="mixed")

            if 'Magnetic_Field' not in df.columns:
                df['Magnetic_Field'] = df.apply(lambda x: np.sqrt(x['bx'] ** 2 + x['by'] ** 2 + x['bz'] ** 2), axis=1)
                df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)

        except Exception as e:
            err_message += [str(e)]

        if len(err_message) == 0:
            save_path = os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\processed"
            if not os.path.exists(save_path):
                os.mkdir(save_path)

            df.to_csv(f'{save_path}\\{dataset_name}.csv')
            # InMermoryDataService.DatasetsService.datasets \
            #     .append(InMermoryDataService.Dataset(name=dataset_name,
            #                                          path=f'{save_path}\\{dataset_name}.csv',
            #                                          dataset_type=InMermoryDataService.DatasetsService \
            #                                          .get_dataset_type_by_name(dataset_type_name),
            #                                          projects=[]))
            return f'{save_path}\\{dataset_name}.csv', None
        else:
            return None, err_message


@callback(
    Output("upload-data-stepper", "active"),
    Output("select_columns_step", "children"),
    Output("review-and-finalize-step", "children"),
    Output("stepper-next-button", "loading"),
    Output("stepper-back-button", "loading"),
    Input("stepper-back-button", "n_clicks"),
    Input("stepper-next-button", "n_clicks"),
    State("upload-data-stepper", "active"),
    State("local", "data"),
    # State variables for all the form fields

    # # ======= SURVEY_DATA FIELDS ========= #
    Input({'type': 'upload-select-dropdown', 'idx': ALL}, 'value'),
    Input({'type': 'upload-checker', 'idx': ALL}, 'checked'),
    Input({'type': 'upload-text-input', 'idx': ALL}, 'value'),
    prevent_initial_call=True
)
def update(back, next_, current, session_store,
           select_state_vars,
           checkbox_state_vars,
           input_state_vars):
    button_id = ctx.triggered_id
    step = current if current is not None else active
    if ctx.triggered[0]['value'] and type(button_id) == str:
        if button_id == "stepper-back-button":
            step = step - 1 if step > min_step else step
        else:
            step = step + 1 if step < max_step else step

        data_content = no_update
        review_and_finalize_content = no_update
        if current == 0:
            data_content = get_upload_data_content(session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED])

        elif current == 1:
            dataset_id = session[AppIDAuthProvider.DATASET_TYPE_SELECTED]
            dataset_name = session[AppIDAuthProvider.DATASET_NAME]
            dataset_type_name = InMermoryDataService.DatasetsService.get_dataset_type_by_id(dataset_id)

            saved_data_path, errors = "", []

            if dataset_type_name == 'SURVEY_DATA':
                data_path = session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED]

                element_ids = ['lat-long', 'latitude', 'longitude', 'easting-northing', 'easting', 'northing', 'zone',
                               'depth-altitude', 'depth', 'altitude', 'extract_depth', 'extract_altitude',
                               'magentic_field', 'datetime']
                element_values = Utils.Utils.get_element_states(ctx.args_grouping, element_ids)

                saved_data_path, errors = save_and_validate_survey_data(
                    dataset_type_name=dataset_type_name,
                    data_path=data_path,
                    dataset_name=dataset_name,
                    lat_long_switch=element_values['lat-long'],
                    latitude=element_values['latitude'],
                    longitude=element_values['longitude'],
                    easting_northing_switch=element_values['easting-northing'],
                    easting=element_values['easting'],
                    northing=element_values['northing'],
                    zone=element_values['zone'],
                    depth_altitude_switch=element_values['depth-altitude'],
                    depth=element_values['depth'],
                    altitude=element_values['altitude'],
                    depth_regex=element_values['extract_depth'],
                    alt_regex=element_values['extract_altitude'],
                    total_field=element_values['magentic_field'],
                    datetime=element_values['datetime']
                )
            elif dataset_type_name == 'OBSERVATORY_DATA':
                if session[AppIDAuthProvider.LAST_DATASET_UPLOADED].split('.')[-1] == 'zip':
                    data_path = os.getcwd() + f"\\data\\{session[AppIDAuthProvider.APPID_USER_NAME]}\\uploaded_zip.csv"
                else:
                    data_path = session[AppIDAuthProvider.LAST_DATASET_UPLOADED]

                element_ids = ['mag_directional', 'magentic_field_obs', 'datetime_obs', 'bx', 'by', 'bz',
                               'datetime-xyz']
                element_values = Utils.Utils.get_element_states(ctx.args_grouping, element_ids)

                saved_data_path, errors = save_and_validate_observatory_data(
                    dataset_name=session[AppIDAuthProvider.DATASET_NAME],
                    dataset_type_name=dataset_type_name,
                    data_path=data_path,
                    observatory_data_switch=element_values['mag_directional'],
                    total_field=element_values['magentic_field_obs'],
                    bx=element_values['bx'], by=element_values['by'], bz=element_values['bz'],
                    datetime=element_values['datetime_obs'],
                    datetime_xyz=element_values['datetime-xyz']
                )

            review_and_finalize_content = get_review_and_finalize_content(saved_data_path, dataset_type_name, session)
            InMermoryDataService.DatasetsService.datasets \
                .append(InMermoryDataService.Dataset(name=dataset_name,
                                                     # path=f'{save_path}\\{dataset_name}.csv',
                                                     path=saved_data_path,
                                                     dataset_type=InMermoryDataService.DatasetsService \
                                                     .get_dataset_type_by_name(dataset_type_name),
                                                     projects=[]))

        else:
            data_content = no_update

        return step, data_content, review_and_finalize_content, False, False
    else:
        return current, no_update, no_update, False, False


def switch_dataset_tab(app: dash.Dash, du):
    @app.callback(Output("content", "children"), [Input("tabs", "active_tab")])
    def switch_dataset_tab(at):
        if at == "file_upload":
            uploader = get_upload_file_tab_content(du, upload_id=session[AppIDAuthProvider.APPID_USER_NAME])
            return uploader
        elif at == "existing_datasets":
            return html.Div([
                html.P('PLACEHOLDER')
            ])
        return html.P("")


clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output("stepper-next-button", "loading", allow_duplicate=True),
    Input("stepper-next-button", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output("stepper-back-button", "loading", allow_duplicate=True),
    Input("stepper-back-button", "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(checked) {
        if (checked) {
            return "show-div"
        } else {
            return "hide-div"
        }
    }
    """,
    Output("lat-long-group", "className", allow_duplicate=True),
    Input({'type': 'upload-checker', 'idx': 'lat-long'}, "checked"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(checked) {
        if (checked) {
            return "show-div"
        } else {
            return "hide-div"
        }
    }
    """,
    Output("easting-northing-group", "className", allow_duplicate=True),
    Input({'type': 'upload-checker', 'idx': 'easting-northing'}, "checked"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(checked) {
        if (checked) {
            return "show-div"
        } else {
            return "hide-div"
        }
    }
    """,
    Output('depth-altitude-group', "className", allow_duplicate=True),
    Input({'type': 'upload-checker', 'idx': 'depth-altitude'}, "checked"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(checked) {
        if (checked) {
            return "show-div"
        } else {
            return "hide-div"
        }
    }
    """,
    Output("magnetic-field-xyz-group", "className", allow_duplicate=True),
    Input({'type': 'upload-checker', 'idx': 'mag_directional'}, "checked"),
    prevent_initial_call=True,
)


@callback(
    Output("observatory-magnetic-field-group", "className", allow_duplicate=True),
    Input({'type': 'upload-checker', 'idx': 'mag_directional'}, "checked"),
    prevent_initial_call=True
)
def hide_total_field_div(checked):
    if checked:
        return "hide-div"
    else:
        return "show-div"


@callback(
    Output('data-table-container', 'children'),
    Output("toast-placeholder-div", "children", allow_duplicate=True),
    Input({'type': 'upload-select-dropdown', 'idx': 'depth'}, 'value'),
    Input({'type': 'upload-select-dropdown', 'idx': 'altitude'}, 'value'),
    State('datatable-datasets', 'data'),
    State({'type': 'upload-text-input', 'idx': 'extract_depth'}, 'value'),
    State({'type': 'upload-text-input', 'idx': 'extract_altitude'}, 'value'),
    prevent_initial_call=True
)
def update_depth_regex_div(depth_col, alt_col, depth_state, depth_regex, alt_regex):
    triggered_id = dash.callback_context.triggered_id['idx']

    try:
        if triggered_id == 'altitude':
            target_col = alt_col
            target_regex = alt_regex
        elif triggered_id == 'depth':
            target_col = depth_col
            target_regex = depth_regex

        if not target_col:
            return no_update, no_update
        current_df = pd.DataFrame(depth_state)
        current_df[f'{target_col}_extracted'] = current_df[target_col].astype(str).str.extract(f"{target_regex}")
    except Exception as e:
        return no_update, Toast.get_toast("Error processing request", f"{str(e)}", "danger")
    return DataTableNative.get_native_datable(current_df), no_update


@callback(
    Output("local", "data", allow_duplicate=True),
    Input("upload-select-dataset", "value"),
    Input("upload-dataset-name", "value"),
    prevent_initial_call=True
)
def update_selected_dataset(sd, d_name):
    patch = Patch()
    session[AppIDAuthProvider.DATASET_TYPE_SELECTED] = sd
    session[AppIDAuthProvider.DATASET_NAME] = d_name
    return patch


def get_select_dropdown(columns, label, dropdown_id, required=True, icon=None):
    select = dmc.Select(
        data=columns,
        label=label,
        id=dropdown_id,
        searchable=True,
        nothingFound="No such column",
        icon=icon,
        persistence=True,
        persistence_type='session',
        persisted_props=['value'],
        placeholder='Select',
        selectOnBlur=True,
        clearable=True,
        required=required
    )

    return select


def get_survey_data_form(df):
    ret_val = [
        # Survey Dataframe: Magnetic Field, Datetime

        dmc.Group(children=[
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Magnetic Field Column",
                                          # dropdown_id='magentic_field_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'magentic_field'},
                                          icon=DashIconify(icon="game-icons:magnet")), radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Datetime column",
                                          # dropdown_id='upload_datetime_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'datetime'},
                                          icon=DashIconify(icon="formkit:datetime")), radius='md', shadow='lg')
        ], grow=True, spacing='lg', id='magnetic-field-group'),

        # Lat Long Group

        dmc.Switch(label="Does your dataset have Latitude and Longitude information?",
                   checked=False,
                   onLabel='YES',
                   offLabel='NO',
                   # id='lat-long-switch',
                   id={'type': 'upload-checker', 'idx': 'lat-long'},
                   size='lg',
                   color='teal',
                   thumbIcon=DashIconify(
                       icon="dashicons:yes-alt", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5]
                   )
                   ),
        dmc.Group(children=[
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Latitude column",
                                          # dropdown_id='upload_latitude_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'latitude'},
                                          icon=DashIconify(icon="mingcute:earth-latitude-fill")),
                      radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Longitude column",
                                          # dropdown_id='upload_longitude_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'longitude'},
                                          icon=DashIconify(icon="mingcute:earth-longitude-line")),
                      radius='md', shadow='lg')
        ], grow=True, spacing='lg', id='lat-long-group', className='hide-div'),

        # Easting Northing Zone Group

        dmc.Switch(label="Does your dataset have Easting and Northing information?",
                   checked=False,
                   onLabel='YES',
                   offLabel='NO',
                   # id='easting-northing-switch',
                   id={'type': 'upload-checker', 'idx': 'easting-northing'},
                   size='lg',
                   color='teal',
                   thumbIcon=DashIconify(
                       icon="dashicons:yes-alt", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5]
                   )
                   ),

        dmc.Group(children=[
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Northing column",
                                          # dropdown_id='upload_northing_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'northing'},
                                          icon=DashIconify(icon="mingcute:earth-latitude-line")),
                      radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Easting column",
                                          # dropdown_id='upload_easting_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'easting'},
                                          icon=DashIconify(icon="mingcute:earth-longitude-line")),
                      radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Zone column",
                                          # dropdown_id='upload_zone_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'zone'},
                                          icon=DashIconify(icon="file-icons:moment-timezone"))
                      , radius='md', shadow='lg')
        ], grow=True, spacing='lg', id='easting-northing-group', className='hide-div'),

        # Depth and / or Altitude columns

        dmc.Switch(label="Does your dataset have Depth and / or Altitude information?",
                   checked=False,
                   onLabel='YES',
                   offLabel='NO',
                   # id='depth-altitude-switch',
                   id={'type': 'upload-checker', 'idx': 'depth-altitude'},
                   size='lg',
                   color='teal',
                   thumbIcon=DashIconify(
                       icon="dashicons:yes-alt", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5]
                   )
                   ),

        dmc.Group(children=[
            dmc.Paper(
                children=[
                    get_select_dropdown(df.columns,
                                        label="Select Depth column",
                                        # dropdown_id='depth-col-selection',
                                        dropdown_id={'type': 'upload-select-dropdown', 'idx': 'depth'},
                                        required=False,
                                        icon=DashIconify(icon="iconoir:depth")),
                    dmc.TextInput(
                        label='Regex to Extract Depth',
                        # id='extract_depth_regex',
                        id={'type': 'upload-text-input', 'idx': 'extract_depth'},
                        radius=5,
                        icon=DashIconify(icon="bi:regex"),
                        placeholder="Depth Extraction Regex",
                        value=r"(?P<target>[0-9]*[\.]{1}[0-9]+|[0-9]*)"
                    )
                ], radius='md', shadow='lg'),
            dmc.Paper(
                children=[
                    get_select_dropdown(df.columns,
                                        label="Select Altitude column",
                                        # dropdown_id='altitude-col-selection',
                                        dropdown_id={'type': 'upload-select-dropdown', 'idx': 'altitude'},
                                        required=False,
                                        icon=DashIconify(icon="mdi:sea-level-rise")),
                    dmc.TextInput(
                        label='Regex to Extract Altitude',
                        # id='extract_alt_regex',
                        id={'type': 'upload-text-input', 'idx': 'extract_altitude'},
                        radius=5,
                        icon=DashIconify(icon="bi:regex"),
                        placeholder="Altitude Extraction Regex",
                        value=r"(?P<target>[0-9]*[\.]{1}[0-9]+|[0-9]*)"
                    )
                ], radius='md', shadow='lg'),
        ], grow=True, spacing='lg', id='depth-altitude-group', className='hide-div')
    ]

    return ret_val


def get_observatory_data_form(df):
    ret_val = [
        dmc.Switch(label="Does your dataset have individual X,Y,Z components of Magnetic Field?",
                   checked=False,
                   onLabel='YES',
                   offLabel='NO',
                   # id='observatory_mag_directional_switch',
                   id={'type': 'upload-checker', 'idx': 'mag_directional'},
                   size='lg',
                   color='teal',
                   thumbIcon=DashIconify(
                       icon="dashicons:yes-alt", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5]
                   )),
        dmc.Group(children=[
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Magnetic Field Column",
                                          # dropdown_id='magentic_field_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'magentic_field_obs'},
                                          icon=DashIconify(icon="game-icons:magnet")), radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Datetime column",
                                          # dropdown_id='upload_datetime_select_dropdown',
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'datetime_obs'},
                                          icon=DashIconify(icon="formkit:datetime")), radius='md', shadow='lg')
        ], grow=True, spacing='lg', id='observatory-magnetic-field-group', className='show-div'),

        dmc.Group(children=[
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Magnetic Field X Component",
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'bx'},
                                          icon=DashIconify(icon="carbon:x-axis")), radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Magnetic Field Y Component",
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'by'},
                                          icon=DashIconify(icon="carbon:y-axis")), radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Magnetic Field Z Component",
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'bz'},
                                          icon=DashIconify(icon="carbon:z-axis")), radius='md', shadow='lg'),
            dmc.Paper(children=
                      get_select_dropdown(df.columns,
                                          label="Select Datetime column",
                                          dropdown_id={'type': 'upload-select-dropdown', 'idx': 'datetime-xyz'},
                                          icon=DashIconify(icon="formkit:datetime")), radius='md', shadow='lg')
        ], grow=True, spacing='lg', id='magnetic-field-xyz-group', className='hide-div')

    ]
    return ret_val


def get_data_cols(session, df):
    dataset_id = session[AppIDAuthProvider.DATASET_TYPE_SELECTED]
    dataset_name = InMermoryDataService.DatasetsService.get_dataset_type_by_id(dataset_id)
    ret_val = None
    if dataset_name == 'SURVEY_DATA':
        ret_val = get_survey_data_form(df)
    elif dataset_name == 'OBSERVATORY_DATA':
        ret_val = get_observatory_data_form(df)

    return ret_val
