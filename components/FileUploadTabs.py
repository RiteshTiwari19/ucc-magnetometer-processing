import os
import shutil
import threading
import time
import uuid
from zipfile import ZipFile

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import dask.array as da
import dask.dataframe as ddf
import pandas as pd
from dash import html, Output, Input, callback, no_update, State, ctx, clientside_callback, Patch, ALL
from dash_iconify import DashIconify
from dask.distributed import Client, LocalCluster
from flask import session

from Celery import background_callback_manager
from api.DatasetService import DatasetService
from api.DatasetTypeService import DatasetTypeService
from api.dto import CreateNewDatasetDTO, CreateDatasetDTO
from auth import AppIDAuthProvider
from components import DashUploader, DataTableNative, Toast, DataUploadSummaryPageComponent, NotificationProvider, \
    DatasetsComponent
from utils import Consts
from utils import Utils
from utils.AzureContainerHelper import BlobConnector

min_step = 0
max_step = 3
active = 0


def get_datasets_skeleton():
    lors = [

               dmc.Paper(dmc.LoadingOverlay(
                   children=[
                       dmc.Stack(
                           spacing="xs",
                           children=[
                               dmc.Skeleton(radius=10, circle=True),
                               dmc.Skeleton(height=10, width="100%", visible=True),
                               dmc.Skeleton(height=10, width="100%", visible=True),
                               dmc.Skeleton(height=10, width="100%", visible=True),
                               dmc.Skeleton(height=10, width="40%", visible=True),
                           ],
                       )],
                   loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
               ), radius='md', shadow='lg', p='md')] * 5

    return dmc.Stack(children=lors, align='stretch', mt='md')


datasets_tabs = \
    dmc.LoadingOverlay(html.Div(
        [
            dbc.Tabs(
                [
                    dbc.Tab(children=get_datasets_skeleton(), label="Existing Datasets", tab_id="existing_datasets",
                            activeTabClassName="fw-bold",
                            activeLabelClassName="text-success",
                            id={'type': 'tab', 'subset': 'dataset', 'idx': 'existing_datasets'}
                            ),
                    dbc.Tab(label="Upload", tab_id="file_upload", activeTabClassName="fw-bold",
                            activeLabelClassName="text-success",
                            id={'type': 'tab', 'subset': 'dataset', 'idx': 'file_upload'}
                            ),
                ],
                id="dataset_tabs",
                active_tab="existing_datasets",
            ),
            html.Div(
                id="content", style={'width': '100%'})
        ],
        style={
            'textAlign': 'center',
            'width': '100%',
            'padding': '10px',
            'display': 'inline-block'
        }
    ),
        loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
    )


def get_upload_file_tab_content(configured_du, upload_id):
    content = html.Div([
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
    data_types = DatasetTypeService.get_dataset_types(session=session)
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
                        children=[dbc.Spinner(children=[
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
                        )],
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


def read_observatory_data(blob_path, session_store):
    cluster = LocalCluster()
    client = Client(cluster)
    dask_df = ddf.read_table(blob_path, assume_missing=True).reset_index()

    cols = list(dask_df.columns) + ['RangeIndex']
    dask_df = dask_df.reset_index()
    dask_df.columns = cols
    dask_df = dask_df[cols[:-1]]

    fraction_to_read = 2000 / dask_df.count().compute()[1]
    dask_df_sample = dask_df.sample(frac=fraction_to_read).compute()

    save_location = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\uploaded_zip.csv"
    dask_df.to_csv(save_location, single_file=True, compute=True)

    shutil.rmtree(os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\extracted\\")

    client.close()
    cluster.close()

    return dask_df_sample.reset_index()


def get_upload_data_content(session_store, data_path):
    selected_path = session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED]
    if data_path:
        if selected_path.endswith('.csv'):
            df = pd.read_csv(session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED]).dropna().sample(2000)
        else:
            if selected_path.endswith('.zip'):
                data_path_file = selected_path.split('/')[-1]
                data_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\{data_path_file}"
                with ZipFile(data_path, 'r') as z_object:
                    extract_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\extracted"
                    if not os.path.exists(extract_path):
                        os.mkdir(extract_path)

                    try:
                        z_object.extractall(path=f"{extract_path}")
                        df = read_observatory_data(f'{extract_path}\\*.txt', session_store)
                        # df = df.loc[:, df.columns[:-1]]
                    except Exception as e:
                        print(e)
                os.remove(data_path)
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

                *get_data_cols(session_store, df)

            ]
            ),
            loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
            style={'flex': '1 1 0', 'maxWidth': '100%'}
        )
    else:
        return html.Div()


def get_review_and_finalize_content(data_path=None,
                                    data_type='SURVEY_DATA',
                                    session_store=None):
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
                                                                      session_store),
                    id='data-table-container'
                )
            ]
            ),
            loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
            style={'flex': '1 1 0', 'maxWidth': '100%'}
        )
    else:
        return html.Div()


def save_and_validate_survey_data(set_progress, session_store,
                                  dataset_type_name, data_path, dataset_name, new_dataset_id, lat_long_switch, latitude, longitude,
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
        if depth:
            col_map[depth] = 'Depth'
        if altitude:
            col_map[altitude] = 'Altitude'

    if len(err_message) > 0:
        return None, err_message
    else:
        observation_dates = None
        try:
            col_map_keys = list(col_map.keys())
            df = pd.read_csv(data_path)[col_map_keys]
            df = df.rename(columns=col_map)

            time.sleep(1.5)
            progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Processing;Performing Type Conversion!"
            set_progress(NotificationProvider.notify(progress_message,
                                                     action='update'))

            df = df[df['Easting'] != '*']
            df['Magnetic_Field'] = df['Magnetic_Field'].astype(float)
            df['Datetime'] = pd.to_datetime(df['Datetime'], format="mixed")

            observation_dates = f'{df["Datetime"].min().strftime("%m/%d/%Y")} - {df["Datetime"].max().strftime("%m/%d/%Y")}'

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
            save_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\processed"
            if not os.path.exists(save_path):
                os.mkdir(save_path)
            df.to_csv(f'{save_path}\\{dataset_name}.csv')

            BlobConnector.upload_blob(blob_name=f'{new_dataset_id}.csv',
                                      user_id=session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID],
                                      local_file_path=f'{save_path}\\{dataset_name}.csv')

            return f'{save_path}\\{dataset_name}.csv', None, observation_dates
        else:
            return None, err_message, None


def save_and_validate_observatory_data(set_progress,
                                       session_store,
                                       dataset_type_name,
                                       dataset_name,
                                       new_dataset_id,
                                       data_path,
                                       observatory_data_switch,
                                       total_field, bx, by, bz, datetime, datetime_xyz):
    err_message = []

    col_map = {}

    cluster = LocalCluster()
    client = Client(cluster)

    time.sleep(1)
    progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Validation;Validating Observatory Data!"
    set_progress(NotificationProvider.notify(progress_message, action="show", notification_id='zip-processor'))
    time.sleep(1)

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
        observation_dates = None
        try:

            col_map_keys = list(col_map.keys())
            print(col_map_keys)

            df = ddf.read_csv(data_path)[col_map_keys] if data_path.endswith('csv') else \
                ddf.read_table(data_path, dtype={'Datetime': str})[col_map_keys]

            print(df.columns)
            df = df.rename(columns=col_map)
            time.sleep(1)
            progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Processing;Parsing Date!"
            set_progress(
                NotificationProvider.notify(progress_message, action="update", notification_id='zip-processor'))
            time.sleep(1)

            df = df.assign(Datetime=ddf.to_datetime(df['Datetime'], format='%d/%m/%Y %H:%M:%S'))
            df = df.assign(Date=df['Datetime'].dt.date)
            print('Assigned Datetime')

            if 'Magnetic_Field' not in df.columns:
                time.sleep(1)
                progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Processing;Computing Total Field!"
                set_progress(
                    NotificationProvider.notify(progress_message, action="update", notification_id='zip-processor'))
                time.sleep(1)
                df = df.assign(Magnetic_Field=da.sqrt(df['bx'] ** 2 + df['by'] ** 2 + df['bz'] ** 2))
                df = df.assign(Magnetic_Field_Smoothed=df['Magnetic_Field']
                               .rolling(window=100, win_type='boxcar', center=True, min_periods=1).mean())
                df = df.assign(Baseline=df['Magnetic_Field_Smoothed'] - df['Magnetic_Field_Smoothed'].mean())

        except Exception as e:
            err_message += [str(e)]
            print(f'Received ERROR WHEN PROC {err_message}')

        if len(err_message) == 0:
            save_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\processed"
            if not os.path.exists(save_path):
                os.mkdir(save_path)

            progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Saving;Saving Observatory Data!"
            set_progress(
                NotificationProvider.notify(progress_message, action="update", notification_id='zip-processor'))
            observation_dates = '{} - {}'.format(df['Datetime'].min().compute().strftime("%m/%d/%Y"),
                                                 df['Datetime'].max().compute().strftime("%m/%d/%Y"))
            df.to_csv(f'{save_path}\\{dataset_name}.csv', single_file=True, compute=True)
            os.remove(data_path)
            client.close()
            cluster.close()

            time.sleep(0.5)
            progress_message = f"{Consts.Consts.FINISHED_DISPLAY_STATE};Done;Saved Observatory Data!"
            set_progress(
                NotificationProvider.notify(progress_message, action="update", notification_id='zip-processor'))
            time.sleep(0.5)

            uploader_thread = threading.Thread(
                target=BlobConnector.upload_blob, kwargs={
                    'blob_name': f'{new_dataset_id}.csv',
                    'user_id': f'{session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID]}',
                    'local_file_path': f'{save_path}\\{dataset_name}.csv'
                })
            uploader_thread.start()

            return f'{save_path}\\{dataset_name}.csv', None, observation_dates
        else:
            return None, err_message, None


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
    progress=Output("notify-container-placeholder-div", "children"),
    prevent_initial_call=True,
    background=True,
    manager=background_callback_manager
)
def update(set_progress, back, next_, current, session_store,
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
            time.sleep(1)
            progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Loading; Reading Dataset!"
            set_progress(NotificationProvider.notify(progress_message, action='show', notification_id='c0'))
            data_content = get_upload_data_content(session_store,
                                                   session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED])

            time.sleep(3)
            progress_message = f"{Consts.Consts.FINISHED_DISPLAY_STATE};Done;Dataset Loaded!"
            set_progress(NotificationProvider.notify(progress_message, action='update', notification_id='c0'))
        elif current == 1:
            dataset_id = session_store[AppIDAuthProvider.DATASET_TYPE_SELECTED]
            dataset_name = session_store[AppIDAuthProvider.DATASET_NAME]
            dataset_type_name = DatasetTypeService.get_dataset_type_by_id(session=session_store,
                                                                          dataset_type_id=dataset_id)

            saved_data_path, errors = "", []
            new_dataset_id = str(uuid.uuid4())

            if dataset_type_name.name == 'SURVEY_DATA':
                time.sleep(2)
                progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Validation;Validating Data!"
                set_progress(NotificationProvider.notify(progress_message, action="show"))
                data_path = session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED]

                element_ids = ['lat-long', 'latitude', 'longitude', 'easting-northing', 'easting', 'northing', 'zone',
                               'depth-altitude', 'depth', 'altitude', 'extract_depth', 'extract_altitude',
                               'magentic_field', 'datetime']
                element_values = Utils.Utils.get_element_states(ctx.args_grouping, element_ids)

                saved_data_path, errors, obs_dates = save_and_validate_survey_data(
                    set_progress,
                    session_store,
                    dataset_type_name=dataset_type_name.name,
                    data_path=data_path,
                    dataset_name=dataset_name,
                    new_dataset_id=new_dataset_id,
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

            elif dataset_type_name.name == 'OBSERVATORY_DATA':
                if session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED].split('.')[-1] == 'zip':
                    data_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\uploaded_zip.csv"
                else:
                    data_path = session_store[AppIDAuthProvider.LAST_DATASET_UPLOADED]

                element_ids = ['mag_directional', 'magentic_field_obs', 'datetime_obs', 'bx', 'by', 'bz',
                               'datetime-xyz']
                element_values = Utils.Utils.get_element_states(ctx.args_grouping, element_ids)

                saved_data_path, errors, obs_dates = save_and_validate_observatory_data(
                    set_progress,
                    session_store,
                    dataset_name=session_store[AppIDAuthProvider.DATASET_NAME],
                    dataset_type_name=dataset_type_name.name,
                    new_dataset_id=new_dataset_id,
                    data_path=data_path,
                    observatory_data_switch=element_values['mag_directional'],
                    total_field=element_values['magentic_field_obs'],
                    bx=element_values['bx'], by=element_values['by'], bz=element_values['bz'],
                    datetime=element_values['datetime_obs'],
                    datetime_xyz=element_values['datetime-xyz']
                )

            if dataset_type_name.name == 'SURVEY_DATA':
                progress_message = f"{Consts.Consts.LOADING_DISPLAY_STATE};Loading;Generating survey region plot!"
                set_progress(NotificationProvider.notify(progress_message, action='update'))

            review_and_finalize_content = get_review_and_finalize_content(saved_data_path, dataset_type_name.name,
                                                                          session_store)

            new_dataset: CreateNewDatasetDTO = CreateNewDatasetDTO()
            dataset_inner: CreateDatasetDTO = CreateDatasetDTO()

            dataset_inner.tags = {'state': 'DETACHED', 'Observation Dates': obs_dates}
            dataset_inner.name = dataset_name
            dataset_inner.dataset_type_id = dataset_id
            dataset_inner.id = new_dataset_id
            dataset_inner.path = f"datasets/{session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID]}/{new_dataset_id}.csv"

            new_dataset.dataset = dataset_inner

            DatasetService.create_new_dataset(dataset=new_dataset, session=session_store)

            if dataset_type_name.name == 'SURVEY_DATA':
                final_progress_message = f"{Consts.Consts.FINISHED_DISPLAY_STATE};Done;Generated survey region plot!"
                set_progress(NotificationProvider.notify(final_progress_message, action='update'))

        else:
            data_content = no_update

        return step, data_content, review_and_finalize_content, False, False
    else:
        return current, no_update, no_update, False, False


def switch_datasets_tab_outer(app: dash.Dash, du):
    @app.callback(
        Output({'type': 'tab', 'subset': 'dataset', 'idx': ALL}, 'children'),
        Input('dataset_tabs', 'active_tab'),
        State('local', 'data'),
    )
    def switch_datasets_tab(at, session_store):

        if at == "file_upload":
            uploader = get_upload_file_tab_content(du, upload_id=session[AppIDAuthProvider.APPID_USER_NAME])
            return no_update, uploader
        elif at == "existing_datasets":
            return DatasetsComponent.get_datasets(session_store=session_store), no_update


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

            if not alt_col or not alt_regex:
                return no_update, no_update

            target_col = alt_col
            target_regex = alt_regex
        elif triggered_id == 'depth':
            if not depth_col or not depth_regex:
                return no_update, no_update
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

    patch[AppIDAuthProvider.DATASET_TYPE_SELECTED] = sd
    patch[AppIDAuthProvider.DATASET_NAME] = d_name

    return patch


def get_select_dropdown(columns, label, dropdown_id, required=True, icon=None):
    select = dmc.Select(
        data=columns,
        label=label,
        id=dropdown_id,
        searchable=True,
        nothingFound="No such column",
        icon=icon,
        persistence=False,
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


def get_data_cols(session_store, df):
    dataset_id = session_store[AppIDAuthProvider.DATASET_TYPE_SELECTED]

    ret_val = None
    dataset_name = DatasetTypeService.get_dataset_type_by_id(session=session_store, dataset_type_id=dataset_id).name
    if dataset_name == 'SURVEY_DATA':
        ret_val = get_survey_data_form(df)
    elif dataset_name == 'OBSERVATORY_DATA':
        ret_val = get_observatory_data_form(df)

    return ret_val
