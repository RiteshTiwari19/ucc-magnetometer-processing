import os
import shutil
import threading
import time
import uuid
from typing import List
from zipfile import ZipFile

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import dash_uploader
import numpy as np
import pandas as pd
from dash import State, html, Input, Output, ALL, callback, clientside_callback, MATCH, callback_context, \
    no_update, Patch
from dash import dcc
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from flask import session
import geopandas as gpd
import plotly.express as px

import AppConfig
from Celery import background_callback_manager
from FlaskCache import cache
from api import ProjectsService
from api.DatasetService import DatasetService
from api.DatasetTypeService import DatasetTypeService
from api.dto import DatasetFilterDTO, DatasetsWithDatasetTypeDTO, DatasetUpdateDTO, CreateNewDatasetDTO, \
    CreateDatasetDTO
from auth import AppIDAuthProvider
from components import Toast, MapboxScatterPlot, DashUploader
from dataservices.RedisQueue import RedisQueue
from utils.AzureContainerHelper import BlobConnector
from utils.Consts import Consts
from utils.ExportUtils import ExportUtils


def get_annotation_page(session, du):
    title = dmc.Center(
        dmc.Title(
            "Label Survey Data",
            order=3,
            style={"color": "#009688"}
        )
    )

    select_dataset_group = dmc.Group([

        html.Div([
            "Project",
            dcc.Dropdown(id='annotate-select-project')
        ], style={'minWidth': '250px'}),

        dmc.Select(
            id='annotation-select-dataset',
            label='Dataset',
            description='Select Dataset',
            data=['Daily Residual', 'Raw Magnetic Field'],
            required=True,
            searchable=True,
            clearable=False,
            disabled=True
        ),
        dmc.Button(
            "Load Data",
            variant='filled',
            color='primary',
            id='load-data-for-annotation',
            disabled=True
        )
    ], align='end', position='center')

    mapbox_plot_div = dmc.LoadingOverlay([
        html.Div(
            dmc.Stack(
                children=[
                    dmc.Skeleton(height=500, width="100%", visible=True),
                ],
                spacing="xs",
            ), id='mapbox-plot-place-holder', style={'width': '100%'})
    ], loaderProps={"variant": "dots", "color": "orange", "size": "xl"}, style={'width': '100%'})

    scatter_plot = html.Div(id='scatter-plot-div', style={'width': '100%'})

    save_group = html.Div(dmc.Group([
        dbc.Button('Export',
                   color='success',
                   download=f'annotated.csv',
                   href='',
                   external_link=True,
                   target="_blank",
                   outline=True,
                   disabled=True,
                   id='export-annotated-dataset-btn',
                   ),
        dmc.Button("Save", variant='filled', color='success', id='save-annotated-dataset-btn'),
    ]), className='fix-bottom-right')

    return dmc.Stack([
        title,
        dmc.Divider(size=3,
                    color='gray', variant='dashed',
                    style={'marginTop': '1em', 'marginBottom': '1.5em', 'width': '100%'}),

        dmc.Text('Select Dataset', style={"fontSize": 19, "color": "#009688"}),

        select_dataset_group,

        html.Br(),

        scatter_plot,

        html.Br(),

        mapbox_plot_div,

        get_upload_annotations_modal(du=du, session=session),

        save_group,

        add_annotations_modal()
    ],
        align='center'
    )


@callback(
    Output('annotate-select-project', 'options'),
    Input('annotate-select-project', 'search_value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def populate_project_options(search_value, local_storage):
    if not search_value or len(search_value) <= 2:
        raise PreventUpdate

    params = {'project_name': search_value}

    options = ProjectsService.ProjectService.fetch_projects(session_store=local_storage, params=params)
    options = [{'label': o.name, 'value': o.id} for o in options]

    return options


@callback(
    Output('annotation-select-dataset', 'data'),
    Output('annotation-select-dataset', 'disabled'),
    Input('annotate-select-project', 'value'),
    Input('local', 'data'),
)
def load_datasets(project_id, local_storage):
    triggered = callback_context.triggered

    if not triggered or not project_id:
        return no_update, no_update

    cache.delete_memoized(ProjectsService.ProjectService.get_project_by_id)
    selected_project = ProjectsService.ProjectService.get_project_by_id(project_id=project_id, session=local_storage)
    datasets = [{'label': d.dataset.name, 'value': d.dataset.id} for d in selected_project.datasets \
                if 'state' in d.dataset.tags and d.dataset.tags['state'] == 'RESIDUALS_COMPUTED']
    return datasets, False


@callback(
    Output('load-data-for-annotation', 'disabled'),
    Input('annotate-select-project', 'value'),
    Input('annotation-select-dataset', 'value'),
    prevent_initial_call=True
)
def manage_load_data_btn_state(project, dataset):
    if not project or not dataset:
        return True
    else:
        return False


@cache.memoize(timeout=50000)
def get_or_download_dataframe(dataset_id, session_store):
    dataset = DatasetService.get_dataset_by_id(dataset_id=dataset_id, session_store=session_store)

    if 'local_path' in dataset.tags and dataset_id in dataset.tags['local_path'] \
            and os.path.exists(dataset.tags['local_path'][dataset.id]):
        ret_df = pd.read_csv(dataset.tags['local_path'][dataset.id])

        unnamed_cols = [col for col in ret_df.columns if 'unnamed' in col.lower()]
        ret_df = ret_df.drop(columns=unnamed_cols)

        if 'Baseline' in ret_df.columns:
            ret_df.rename(columns={'Baseline': 'Residuals'}, inplace=True)

        return ret_df

    download_path = ExportUtils.download_data_if_not_exists(dataset_path=dataset.path,
                                                            dataset_id=dataset.id,
                                                            session=session_store)
    dataset_tags = dataset.tags or {}
    if 'local_path' not in dataset.tags:
        dataset_tags['local_path'] = {f'{dataset.id}': download_path}
    else:
        dataset_tags['local_path'][dataset.id] = download_path

    updated_dataset = DatasetService.update_dataset(dataset_id=dataset.id,
                                                    session_store=session_store,
                                                    dataset_update_dto=DatasetUpdateDTO(tags=dataset_tags))
    ret_df = pd.read_csv(download_path)
    unnamed_cols = [col for col in ret_df.columns if 'unnamed' in col.lower()]
    ret_df = ret_df.drop(columns=unnamed_cols)

    if 'Baseline' in ret_df.columns:
        ret_df.rename(columns={'Baseline': 'Residuals'}, inplace=True)

    return ret_df


@callback(
    Output('mapbox-plot-place-holder', 'children'),
    Output('scatter-plot-div', 'children'),
    Output('local', 'data', allow_duplicate=True),
    Input('load-data-for-annotation', 'n_clicks'),
    State('annotation-select-dataset', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def load_mapbox_plot(load_data, selected_dataset, local_storage):
    triggered = callback_context.triggered_id
    if not triggered or triggered != 'load-data-for-annotation' or not load_data:
        raise PreventUpdate
    else:
        ctas = get_filter_cta_buttons()
        df = get_or_download_dataframe(dataset_id=selected_dataset, session_store=local_storage)

        mapbox_plot = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None,
                                                        col_to_plot='Residuals',
                                                        points_to_clip=[])

        aside = dmc.Stack([dmc.Aside(
            p="xs",
            width={"base": 45},
            height=200,
            fixed=True,
            position={"right": 20, "top": "50%"},
            children=dmc.Stack([
                dmc.Tooltip(
                    label='Import Annotations',
                    transition="slide-right",
                    transitionDuration=300,
                    children=dmc.ActionIcon(
                        DashIconify(icon='flat-color-icons:import', width=30,
                                    id='import-annotation-side-action-item'),
                        size="md",
                        disabled=False,
                        id='import-annotations'
                    )
                ),
                dmc.Tooltip(
                    label='Show residuals in line plot',
                    transition="slide-right",
                    transitionDuration=300,
                    children=dmc.ActionIcon(
                        DashIconify(icon='mdi:interaction-tap', width=30, color='dark-gray',
                                    id='jump-plot-side-panel-anno'),
                        size="md",
                        id='jump-plot-side-panel-btn-anno',
                        disabled=True
                    )
                ),
                dmc.Tooltip(
                    label='Reset Annotations',
                    transition="slide-right",
                    transitionDuration=300,
                    children=dmc.ActionIcon(
                        DashIconify(icon='icon-park:delete', width=30, color='dark-gray',
                                    id='label-data-side-action-item'),
                        size="md",
                        id='delete-annotatation-side-panel',
                        disabled=False
                    )
                ),
                dmc.Tooltip(
                    label='Annotate Selected Points',
                    transition="slide-right",
                    transitionDuration=300,
                    children=dmc.ActionIcon(
                        DashIconify(icon='foundation:annotate', width=30, color='dark-gray',
                                    id='annotate-data-side-action-item'),
                        size="md",
                        id='annotate-points-side-side-panel',
                        disabled=True
                    )
                )
            ], mt='5px', align='center'),
        )])

        patch = Patch()
        patch[AppConfig.WORKING_DATASET] = selected_dataset

        return dmc.Stack([
            ctas,
            dcc.Graph(figure=mapbox_plot, style={'width': '100%'}, id={'type': 'plotly', 'index': 'annotate-map-plot'}),
            aside

        ], style={'width': '100%'}), dmc.Stack(
            get_residual_scatter_plot(df_id=selected_dataset, session_store=session, col_to_plot='Residuals'),
            style={'width': '100%'}
        ), patch


def get_filter_cta_buttons():
    fiter_cta_buttons = dmc.Stack([
        dmc.Center(
            dmc.Text("Show Filtered Residuals",
                     style={"fontSize": 19, "color": "#009688"})
        ),

        dmc.Group([
            dmc.NumberInput(
                label="Min Residual",
                description="Minimum value of Residuals to filter on",
                value=0,
                step=5,
                min=0,
                id='min-residual-value-filter-anno'
            ),
            dmc.NumberInput(
                label="Max Residual",
                description="Maximum value of Residuals to filter on",
                value=0,
                step=5,
                min=0,
                id='max-residual-value-filter-anno'
            ),

            dmc.Button(
                'Filter',
                variant='outline',
                color='primary',
                id='filter-residual-button-anno'
            ),

            dmc.Button(
                'Reset Filter',
                variant='filled',
                color='wine-red',
                id='reset-residual-filter-button-anno'
            )

        ], grow=True, align='end'),
    ], style={'width': '100%'})

    return fiter_cta_buttons


clientside_callback(
    """
    function(min_val, max_val) {
        if ( isNaN(min_val) | isNaN(max_val) | min_val === "" | max_val === "" ) {
            return true;
        } else {
            if (parseFloat(min_val) >= parseFloat(max_val)) {
                return true;
            } else {
                return false;
            }
        }
    }
    """,
    Output('filter-residual-button-anno', 'disabled'),
    Input('min-residual-value-filter-anno', 'value'),
    Input('max-residual-value-filter-anno', 'value')
)


@callback(
    Output({'type': 'plotly', 'index': 'annotate-map-plot'}, 'figure'),
    Output('modal-import-annotations', 'opened'),
    Input('filter-residual-button-anno', 'n_clicks'),
    Input('reset-residual-filter-button-anno', 'n_clicks'),
    Input('import-annotations-btn', 'n_clicks'),
    State('min-residual-value-filter-anno', 'value'),
    State('max-residual-value-filter-anno', 'value'),
    State('annotation-select-dataset', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def filter_residuals(show_filtered_residuals, reset_filtered_residuals, import_annotation,
                     min_residual, max_residual, selected_dataset,
                     local_storage):
    triggered = callback_context.triggered_id

    trigger_condition = [(triggered == 'filter-residual-button-anno' and show_filtered_residuals),
                         (triggered == 'reset-residual-filter-button-anno' and reset_filtered_residuals),
                         (triggered == 'import-annotations-btn' and import_annotation)
                         ]

    if not triggered or not any(trigger_condition):
        return no_update

    if triggered == 'reset-residual-filter-button-anno':
        if f'{AppConfig.ANNOTATION}__{selected_dataset}__MIN_RESIDUAL' in session:
            del session[f'{AppConfig.ANNOTATION}__{selected_dataset}__MIN_RESIDUAL']
        if f'{AppConfig.ANNOTATION}__{selected_dataset}__MAX_RESIDUAL' in session:
            del session[f'{AppConfig.ANNOTATION}__{selected_dataset}__MAX_RESIDUAL']

        cache.delete_memoized(MapboxScatterPlot.get_mapbox_plot_annotated)

    df = get_or_download_dataframe(dataset_id=selected_dataset, session_store=local_storage)

    if triggered == 'filter-residual-button-anno':
        session[f'{AppConfig.ANNOTATION}__{selected_dataset}__MIN_RESIDUAL'] = min_residual
        session[f'{AppConfig.ANNOTATION}__{selected_dataset}__MAX_RESIDUAL'] = max_residual
        cache.delete_memoized(MapboxScatterPlot.get_mapbox_plot_annotated)

    mapbox_plot = MapboxScatterPlot.get_mapbox_plot_annotated(
        df=df,
        col_to_plot='Residuals',
        session_store=local_storage,
        selected_dataset=selected_dataset,
    )

    modal_out = False if triggered == 'import-annotations-btn' and import_annotation else no_update

    return mapbox_plot, modal_out


def get_upload_annotations_modal(du, session):
    uploader = html.Div(DashUploader.get_upload_component(du,
                                                          upload_id=f'{session[AppIDAuthProvider.APPID_USER_BACKEND_ID]}__annotations-uploader'),
                        id='annotation-dash_uploader-div')

    modal = dmc.Modal(
        title="Import Labels",
        id="modal-import-annotations",
        zIndex=10000,
        opened=False,
        size="50%",
        centered=True,
        children=[
            dmc.Stack([
                uploader,
                dmc.Space(h=12),
                dmc.Group(dmc.Button(
                    "Load Annotations",
                    variant='outline',
                    color='info',
                    id='select-annotation-columns-modal-btn'
                ), position='center'),

                dmc.Space(h=12),

                dmc.Space(h=20),
                dmc.Group(
                    [
                        dmc.Button("Import",
                                   id='import-annotations-btn'),
                        dmc.Button(
                            "Close",
                            color="red",
                            variant="outline",
                            id="close-annotations-modal-btn",
                        ),
                    ],
                    position="right",
                ),
            ])
        ],
    )

    return modal


def add_annotations_modal():
    modal = dmc.Modal(
        title="Annotate",
        id="add-annotations-modal",
        zIndex=10000,
        opened=False,
        size="50%",
        centered=True,
        children=[
            dmc.Stack([
                dmc.Select(
                    label='Anomaly Class',
                    data=['Shipwreck', 'UXO', 'Turn', 'Other'],
                    clearable=False,
                    searchable=False,
                    id='annotation-class-select'
                ),
                dmc.Group(
                    [
                        dmc.Button("Label Anomaly",
                                   id='add-annotation-modal-btn'),
                        dmc.Button(
                            "Close",
                            color="red",
                            variant="outline",
                            id="close-annotation-modal-btn",
                        ),
                    ],
                    position="right",
                ),
            ])
        ],
    )

    return modal


@callback(
    Output('local', 'data', allow_duplicate=True),
    Input('add-annotation-modal-btn', 'n_clicks'),
    State({'type': ALL, 'index': 'annotate-residual-plot'}, "selectedData"),
    State('annotation-class-select', "value"),
    State('local', 'data'),
    prevent_initial_call=True
)
def save_annotation_point(clicked, selected_points, selected_label, local_storage):
    triggered = callback_context.triggered_id
    if not clicked or triggered != 'add-annotation-modal-btn' or not len(selected_points):
        raise PreventUpdate
    selected_points = selected_points[0]
    patch = Patch()

    indices = [sd['x'] for sd in selected_points['points']]
    anomaly_start_index = [np.min(indices)]
    anomaly_end_index = [np.max(indices)]
    selected_label = [selected_label]

    selected_dataset = local_storage[AppConfig.WORKING_DATASET]

    if AppConfig.ANNOTATION not in local_storage:
        patch[AppConfig.ANNOTATION] = {}

    if AppConfig.ANNOTATION in local_storage and selected_dataset not in AppConfig.ANNOTATION:
        patch[AppConfig.ANNOTATION][selected_dataset] = {}

    if AppConfig.ANNOTATION in local_storage and selected_dataset in local_storage[AppConfig.ANNOTATION] and \
            'Start' in local_storage[AppConfig.ANNOTATION][selected_dataset]:
        patch[AppConfig.ANNOTATION][selected_dataset]['Start'].extend(anomaly_start_index)
        patch[AppConfig.ANNOTATION][selected_dataset]['End'].extend(anomaly_end_index)
        patch[AppConfig.ANNOTATION][selected_dataset]['Label'].extend(selected_label)
    else:
        patch[AppConfig.ANNOTATION][selected_dataset]['Start'] = np.array(anomaly_start_index)
        patch[AppConfig.ANNOTATION][selected_dataset]['End'] = np.array(anomaly_end_index)
        patch[AppConfig.ANNOTATION][selected_dataset]['Label'] = np.array(selected_label)

    return patch


clientside_callback(
    """
    function(nc1, nc2, opened) {
        return opened ? false: true
    }
    """,
    Output("add-annotations-modal", "opened", allow_duplicate=True),
    Input("add-annotation-modal-btn", "n_clicks"),
    Input('close-annotation-modal-btn', 'n_clicks'),
    State("add-annotations-modal", "opened"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(nc1, nc2, opened) {
        return opened ? false: true
    }
    """,
    Output("modal-import-annotations", "opened", allow_duplicate=True),
    Input("close-annotations-modal-btn", "n_clicks"),
    Input('import-annotations-btn', 'n_clicks'),
    State("modal-import-annotations", "opened"),
    prevent_initial_call=True,
)


@callback(
    Output("modal-import-annotations", "opened", allow_duplicate=True),
    Input('import-annotations', 'n_clicks'),
    prevent_initial_call=True
)
def open_import_annotations_modal(btn_clicked):
    if not btn_clicked:
        raise PreventUpdate
    else:
        return True


@callback(
    # Output('select-label-column-btn', 'disabled'),
    # Output('select-lon-east-column-btn', 'disabled'),
    # Output('select-lat-nort-column-btn', 'disabled'),
    # Output('select-label-column-btn', 'data'),
    # Output('select-lon-east-column-btn', 'data'),
    # Output('select-lat-nort-column-btn', 'data'),
    Output('local', 'data'),
    Output("select-annotation-columns-modal-btn", "loading", allow_duplicate=True),
    Input('select-annotation-columns-modal-btn', 'n_clicks'),
    State('annotation-select-dataset', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def display_col_selection_group(btn_clicked, selected_dataset, local_storage):
    triggered = callback_context.triggered_id

    if not triggered or triggered != 'select-annotation-columns-modal-btn' or not btn_clicked:
        raise PreventUpdate
    else:
        last_file_uploaded = session[AppIDAuthProvider.LAST_DATASET_UPLOADED]
        data_path_file = last_file_uploaded.split('/')[-1]
        data_file_name = data_path_file.split('.')[0]

        is_zip = last_file_uploaded.endswith('.zip')

        data_folder = os.path.join(
            AppConfig.PROJECT_ROOT,
            "data",
            f'{session[AppIDAuthProvider.APPID_USER_BACKEND_ID]}__annotations-uploader'
        )

        data_path = os.path.join(
            data_folder,
            data_path_file
        )

        move_folder_name = str(uuid.uuid4())

        move_folder = os.path.join(
            AppConfig.PROJECT_ROOT,
            "data",
            session[AppIDAuthProvider.APPID_USER_NAME],
            "imported",
            move_folder_name
        )

        move_path = os.path.join(move_folder, f"{move_folder_name}.zip" if is_zip else f"{move_folder_name}.csv")

        if not os.path.exists(move_folder):
            os.mkdir(move_folder)

        shutil.move(src=data_path, dst=move_path)
        shutil.rmtree(data_folder)

        # group_hide = "show-div-flex"
        # ret_cols = [[], [], []]
        # disabled = [True, True, True]

        if is_zip:
            extracted_path = extract_zip_file(move_path, move_folder_name)
            shape_file = [file for file in os.listdir(
                os.path.join(extracted_path, data_file_name)) if str(file).endswith('shp')][0]
            df = gpd.read_file(os.path.join(extracted_path, data_file_name, shape_file))
            # ret_cols[0] = list(df.columns)
            # disabled[0] = False
        else:
            df = pd.read_csv(move_path)
            # ret_cols[0], ret_cols[1], ret_cols[2] = list(df.columns), list(df.columns), list(df.columns)
            # disabled = [False] * 3

        patch = Patch()

        if AppConfig.ANNOTATION not in local_storage:
            patch[AppConfig.ANNOTATION] = {}

        if AppConfig.ANNOTATION in local_storage and selected_dataset not in local_storage[AppConfig.ANNOTATION]:
            patch[AppConfig.ANNOTATION][selected_dataset] = {}

        if AppConfig.ANNOTATION in local_storage and selected_dataset in local_storage[AppConfig.ANNOTATION] \
                and 'Latitude' in local_storage[AppConfig.ANNOTATION][selected_dataset]:
            patch[AppConfig.ANNOTATION][selected_dataset]['Longitude'].extend(list(np.array(df['Longitude'])))
            patch[AppConfig.ANNOTATION][selected_dataset]['Latitude'].extend(list(np.array(df['Latitude'])))
            patch[AppConfig.ANNOTATION][selected_dataset]['Class'].extend(list(np.array(df['Class'])))
            patch[AppConfig.ANNOTATION][selected_dataset]['Type'].extend(list(np.array(df['Type'])))
        else:
            patch[AppConfig.ANNOTATION][selected_dataset]['Longitude'] = np.array(df['Longitude'])
            patch[AppConfig.ANNOTATION][selected_dataset]['Latitude'] = np.array(df['Latitude'])
            patch[AppConfig.ANNOTATION][selected_dataset]['Class'] = np.array(df['Class'])
            patch[AppConfig.ANNOTATION][selected_dataset]['Type'] = np.array(df['Type'])

        return patch, False


def extract_zip_file(data_path, move_folder_name):
    with ZipFile(data_path, 'r') as z_object:
        extract_path = os.path.join(
            AppConfig.PROJECT_ROOT,
            "data",
            session[AppIDAuthProvider.APPID_USER_NAME],
            "imported",
            move_folder_name
        )

        if not os.path.exists(extract_path):
            os.mkdir(extract_path)

        try:
            z_object.extractall(path=f"{extract_path}")
        except Exception as e:
            print(e)
    os.remove(data_path)
    return extract_path


@callback(
    Output('local', 'data', allow_duplicate=True),
    Output('filter-residual-button-anno', 'n_clicks', allow_duplicate=True),
    Input('delete-annotatation-side-panel', 'n_clicks'),
    State('annotation-select-dataset', 'value'),
    State('filter-residual-button-anno', 'n_clicks'),
    State('local', 'data'),
    prevent_initial_call=True
)
def remove_annotations_from_session(delete_annotation, selected_dataset, current_clicks, local_storage):
    if callback_context.triggered_id != 'delete-annotatation-side-panel' or not delete_annotation:
        return no_update, no_update

    current_clicks = current_clicks or 0
    current_clicks = current_clicks + 1

    patch = Patch()
    if AppConfig.ANNOTATION in local_storage and selected_dataset in local_storage[AppConfig.ANNOTATION]:
        del patch[AppConfig.ANNOTATION][selected_dataset]
        return patch, current_clicks
    else:
        return no_update, current_clicks


clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output("select-annotation-columns-modal-btn", "loading"),
    Input("select-annotation-columns-modal-btn", "n_clicks"),
    prevent_initial_call=True,
)


@cache.memoize(timeout=5000)
def get_residual_scatter_plot(df_id, session_store, col_to_plot):
    # df_id = session_store[AppConfig.WORKING_DATASET]

    df = get_or_download_dataframe(dataset_id=df_id, session_store=session_store)

    fig_residual = px.scatter(df.reset_index().iloc[0:50000], x='index', y=col_to_plot,
                              labels={
                                  "index": "Index",
                                  col_to_plot: col_to_plot.replace('_', ' '),
                              }, title="Residuals vs Recording Index"
                              )
    colors = df.reset_index().loc[0:50000, 'Residuals']

    fig_residual.data[0].update(mode='lines+markers')
    fig_residual.update_layout(template='plotly_dark')
    fig_residual.update_traces(marker={'size': 2, 'color': colors, 'showscale': True, 'colorscale': 'Viridis'})

    return dcc.Graph(figure=fig_residual, style={'width': '100%'},
                     id={'type': 'plotly', 'index': 'annotate-residual-plot'})


@callback(
    Output("jump-plot-side-panel-btn-anno", "disabled"),
    Output("jump-plot-side-panel-anno", "color"),
    Input({'type': 'plotly', 'index': 'annotate-map-plot'}, "selectedData"),
)
def enable_jump_plot(selected_points):
    if selected_points and len(selected_points['points']) > 0:
        return False, "blue"
    else:
        return True, "gray"


@callback(
    Output("annotate-points-side-side-panel", "disabled"),
    Output("annotate-data-side-action-item", "color"),
    Output("toast-placeholder-div", "children", allow_duplicate=True),
    Input({'type': 'plotly', 'index': 'annotate-residual-plot'}, "selectedData"),
    prevent_initial_call=True
)
def enable_annotate_button(selected_points):
    if selected_points and len(selected_points['points']) > 0:
        indices = [sd['x'] for sd in selected_points['points']]
        return False, "green", Toast.get_toast("Points Selected",
                                               f'Selected {np.max(indices) - np.min(indices)} points')
    else:
        return True, "gray", no_update


@callback(
    Output('add-annotations-modal', 'opened'),
    Input("annotate-points-side-side-panel", "n_clicks"),
)
def open_annotate_modal(clicked):
    triggered = callback_context.triggered_id
    if not clicked or triggered != 'annotate-points-side-side-panel':
        raise PreventUpdate
    return True


@callback(
    Output({'type': 'plotly', 'index': 'annotate-residual-plot'}, 'figure'),
    Input('jump-plot-side-panel-btn-anno', 'n_clicks'),
    State({'type': 'plotly', 'index': 'annotate-map-plot'}, "selectedData"),
    State('annotation-select-dataset', 'value'),
    State('local', "data"),
    prevent_initial_call=True
)
def patch_figure(clicked, selected_points, dataset_selected, session_store):
    if not clicked:
        raise PreventUpdate

    if selected_points and len(selected_points) > 0 and clicked:
        mod_dict = {sd['customdata'][0]: sd['customdata'][1] for sd in selected_points['points'] if 'customdata' in sd}
        sorted_dict = sorted(mod_dict.items(), key=lambda x: abs(x[1]), reverse=True)[0]

        df_resid = get_or_download_dataframe(dataset_id=dataset_selected, session_store=session_store)

        patch = Patch()

        min_index = max(0, sorted_dict[0] - 25000)
        max_index = min(len(df_resid), min_index + 50000)

        patch['data'][0]['x'] = df_resid.reset_index().loc[min_index:max_index, 'index'].to_numpy()
        patch['data'][0]['y'] = df_resid.reset_index().loc[min_index:max_index, 'Residuals'].to_numpy()
        patch['data'][0]['marker']['color'] = df_resid.reset_index().loc[min_index:max_index, 'Residuals'].to_numpy()
        patch['data'][0]['marker']['showscale'] = True

        patch['layout']['annotations'] = [dict(
            x=sorted_dict[0],
            y=sorted_dict[1],
            text="Point with max residual from the selected points",
            showarrow=True,
            arrowhead=1,
        )
        ]
        print(f'Updated plot: {sorted_dict}')
    else:
        patch = Patch()
        patch['layout']['annotations'].clear()
    return patch


def get_annotated_df(dataset_id, session_store):
    df = get_or_download_dataframe(dataset_id=dataset_id, session_store=session_store).reset_index()
    df['Label'] = 'BACKGROUND'

    if AppConfig.ANNOTATION in session_store and dataset_id in session_store[AppConfig.ANNOTATION]:
        annotations = session_store[AppConfig.ANNOTATION][dataset_id]
    else:
        annotations = {}

    annotations = {k: annotations[k] for k in ('Start', 'End', 'Label')}

    annotations = pd.DataFrame(annotations)

    for index, row in annotations.iterrows():
        df.loc[row['Start']:row['End'], 'Label'] = row['Label']

    return df


clientside_callback(
    """
    function set_loading_state(n_clicks) {
        return true
    }
    """,
    Output('save-annotated-dataset-btn', 'loading'),
    Input('save-annotated-dataset-btn', 'n_clicks'),
    prevent_initial_call=True
)


@callback(
    Output('export-annotated-dataset-btn', 'href', allow_duplicate=True),
    Output('export-annotated-dataset-btn', 'disabled', allow_duplicate=True),
    Output('save-annotated-dataset-btn', 'loading', allow_duplicate=True),
    Input('save-annotated-dataset-btn', 'n_clicks'),
    State('annotate-select-project', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def save_annotated_dataset(save_button, project_id, local_storage):
    triggered = callback_context.triggered_id
    if triggered != 'save-annotated-dataset-btn' or not save_button or not project_id or project_id == '':
        raise PreventUpdate

    is_update = False

    active_project = ProjectsService.ProjectService.get_project_by_id(session=local_storage, project_id=project_id)

    existing_dataset_id = None
    existing_tags = None
    for dat in active_project.datasets:
        if dat.dataset.tags['state'] == 'ANNOTATED':
            is_update = True
            existing_dataset_id = dat.dataset.id
            existing_tags = dat.dataset.tags

    new_dataset_id = str(uuid.uuid4()) if not is_update else existing_dataset_id

    parent_dataset_id = local_storage[AppConfig.WORKING_DATASET]

    annotated_df = get_annotated_df(dataset_id=parent_dataset_id, session_store=local_storage)

    save_location = os.path.join(
        AppConfig.PROJECT_ROOT,
        'data',
        local_storage[AppIDAuthProvider.APPID_USER_NAME],
        'exported',
        f"{new_dataset_id}.csv"
    )

    annotated_df.to_csv(save_location)

    parent_dataset = DatasetService.get_dataset_by_id(dataset_id=parent_dataset_id, session_store=local_storage)
    azr_path = '{}.csv'.format(new_dataset_id)

    try:
        if not is_update:

            link_state = 'ANNOTATED'
            tags = {'state': link_state}
            tags['export'] = {'CSV': f'{new_dataset_id}.csv'}

            if 'Observation Dates' in parent_dataset.tags:
                tags['Observation Dates'] = parent_dataset.tags['Observation Dates']

            new_dataset: CreateNewDatasetDTO = CreateNewDatasetDTO(
                dataset=CreateDatasetDTO(
                    parent_dataset_id=parent_dataset_id,
                    id=new_dataset_id,
                    name=parent_dataset.name,
                    dataset_type_id=parent_dataset.dataset_type.id,
                    project_id=project_id,
                    path=f"datasets/{local_storage[AppIDAuthProvider.APPID_USER_BACKEND_ID]}/{new_dataset_id}.csv",
                    tags=tags
                ),
                project_dataset_state=link_state
            )
            created_dataset = DatasetService.create_new_dataset(dataset=new_dataset, session=local_storage)
        else:
            print(f'Updating existing Annotated dataset with id: {new_dataset_id}')
            updated_dataset = DatasetService.update_dataset(dataset_id=existing_dataset_id,
                                                            session_store=local_storage,
                                                            dataset_update_dto=DatasetUpdateDTO(
                                                                tags=existing_tags))

        uploader_thread = threading.Thread(
            target=BlobConnector.upload_blob, kwargs={
                'blob_name': azr_path,
                'user_id': local_storage[AppIDAuthProvider.APPID_USER_BACKEND_ID],
                'local_file_path': save_location,
                'linked': False
            })
        uploader_thread.start()

        cache.delete_memoized(DatasetService.get_dataset_by_id)
        cache.delete_memoized(ProjectsService.ProjectService.get_project_by_id)

        session[AppConfig.WORKING_DATASET] = new_dataset_id

        href = '/download/{}.{}'.format(new_dataset_id, 'CSV')

        return href, False, False
    except:
        pass
