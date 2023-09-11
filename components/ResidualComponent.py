import os
import shutil
import threading
import time
import uuid

import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import plotly.express as px
from dash import dcc, html, Input, Output, State, no_update, ALL, callback, clientside_callback, \
    callback_context
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from flask import session
from dash import Patch

import AppConfig
from FlaskCache import cache
from api import ResidualService
from api.DatasetService import DatasetService
from api.ProjectsService import ProjectService
from api.dto import DatasetResponse, DatasetUpdateDTO, CreateNewDatasetDTO, CreateDatasetDTO
from auth import AppIDAuthProvider
from components import ModalComponent, MapboxScatterPlot
from dataservices import InMermoryDataService
from utils.AzureContainerHelper import BlobConnector
from utils.ExportUtils import ExportUtils


def get_page_tags(active_project, session_store, tags_to_add: dict = None, skip_extra_styling=False):
    if tags_to_add:
        for k, v in tags_to_add.items():
            active_project.tags[k] = v

    tag_buttons = generate_tag_badges(active_project, session_store, skip_extra_styling=skip_extra_styling)

    return tag_buttons


def get_mag_data_page(session, configured_du):
    active_project = ProjectService.get_project_by_id(project_id=session['current_active_project'],
                                                      session=session)
    active_session = session[AppIDAuthProvider.APPID_USER_NAME]
    datasets = InMermoryDataService.DatasetsService.get_existing_datasets()
    drop_down_options = [{'label': dataset.name, 'value': dataset.name} for dataset in datasets]

    df, scatter, map_box = get_residual_scatter_plot(session_store=session, col_to_plot='Magnetic_Field')

    mag_data_page = html.Div([
        html.Div(ModalComponent.get_upload_data_modal(configured_du,
                                                      upload_id=session[AppIDAuthProvider.APPID_USER_NAME]),
                 style={'width': '100%'}),
        html.Div(get_page_tags(active_project, tags_to_add={
            'Stage': 'Residual'
        }, session_store=session, skip_extra_styling=True), id='mag-data-tags-div',
                 style={
                     'display': 'flex',
                     'flexDirection': 'row',
                     'flexWrap': 'wrap',
                     'alignItems': 'space-between',
                     'justifyContent': 'flex-start'
                 }),
        html.Div(id="selected-data-div"),
        dmc.Divider(size=4, color='gray', variant='dashed', style={'marginTop': '1em', 'marginBottom': '1.2em'}),
        dmc.Group([
            dmc.Stack(
                children=[
                    dmc.Badge("Ambient Smoothing Constant", color="wine-red", className="ms-1", variant='color',
                              style={'maxWidth': '50%'}),
                    dmc.Slider(
                        id="ambient-smoothing-slider",
                        value=500,
                        updatemode="drag",
                        min=0,
                        max=1000,
                        color='wine-red',
                        size='lg',
                        radius=10,
                        labelTransitionTimingFunction='ease',
                        labelTransition='scale-x',
                        labelTransitionDuration=600,
                        marks=[{'label': i, "value": i} for i in np.arange(100, 1000, 100)],
                        style={'width': '100%'}, ),
                    dmc.Space(h=15)
                ],
                style={'width': '40%'}),

            dmc.Stack([
                dmc.Badge("Observed Smoothing Constant", color="cyan", className="ms-1", variant='color',
                          style={'maxWidth': '50%'}),
                dmc.Slider(
                    id="observed-smoothing-slider",
                    value=100,
                    updatemode="drag",
                    min=0,
                    max=200,
                    color='cyan',
                    labelTransitionTimingFunction='ease',
                    labelTransition='scale-x',
                    labelTransitionDuration=600,
                    size='lg',
                    radius=10,
                    marks=[{'label': i, "value": i} for i in np.arange(10, 200, 20)],
                    style={'width': '100%'}
                ),
                dmc.Space(h=15)
            ], style={'width': '40%'}),

            dmc.Button("Apply", variant='outline', color='secondary', id='calc-residuals-btn')

        ], spacing='lg', className='show-div', id='smoothing-constant-div', position='center'),

        dmc.Space(h='lg'),

        dmc.Group([
            dmc.Switch(label="Display one plot per row?",
                       checked=False,
                       onLabel='YES',
                       offLabel='NO',
                       id='grid-conf',
                       size='lg',
                       color='teal',
                       thumbIcon=DashIconify(
                           icon="dashicons:yes-alt", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5])
                       ),

            html.Div(
                dmc.Switch(label="Show residuals only?",
                           checked=False,
                           onLabel='YES',
                           offLabel='NO',
                           id='show-residuals-switch',
                           size='lg',
                           color='teal',
                           thumbIcon=DashIconify(
                               icon="dashicons:yes-alt", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5])
                           ),
                className='hide-div', id='show-residuals-div'),
        ]),

        html.Br(),

        dmc.Group(children=[
            dmc.TextInput(label="Min Value",
                          id='clip-min',
                          value=df['Magnetic_Field'].quantile(0.10),
                          icon=DashIconify(
                              icon="fluent-mdl2:minimum-value", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5])
                          ),
            dmc.TextInput(label="Max Value",
                          id='clip-max',
                          value=df['Magnetic_Field'].quantile(0.90),
                          icon=DashIconify(
                              icon="fluent-mdl2:maximum-value", width=16, color=dmc.theme.DEFAULT_COLORS["teal"][5])
                          ),

            dmc.Button("Clip", leftIcon=DashIconify(icon='mdi:clip', color='wine-red'),
                       id='clip-button', variant='outline', disabled=True),

            dmc.Button("Reset Clip", leftIcon=DashIconify(icon='bx:reset', color='wine-red'),
                       id='reset-clp-btn', variant='filled', color='blue'),
        ],
            id='clip-cta-parent', align='end', position='center'),

        html.Br(),

        dmc.Aside(
            p="xs",
            width={"base": 45},
            height=100,
            fixed=True,
            position={"right": 20, "top": "50%"},
            children=dmc.Stack([
                dmc.ActionIcon(
                    DashIconify(icon='mdi:clip', width=30, color='dark-gray',
                                id='side-panel-clip-color'),
                    size="md",
                    disabled=True,
                    id='clip-side-panel'
                ),
                dmc.ActionIcon(
                    DashIconify(icon='mdi:interaction-tap', width=30, color='dark-gray',
                                id='side-panel-jump-color'),
                    size="md",
                    id='jump-plot-side-panel',
                    disabled=True
                )
            ], mt='5px', align='center'),
        ),

        html.Div(
            children=[
                dmc.LoadingOverlay(children=
                [
                    html.Div(id='datasets-residuals-plot', style={'flex': 'auto'},
                             children=dmc.Stack(
                                 spacing="xs",
                                 children=[
                                     dcc.Graph(figure=scatter)

                                 ],
                             )
                             ),
                    html.Br(),
                    dmc.Group(
                        [
                            dmc.Tooltip(
                                dmc.Button("Previous", variant="outline", id='show-previous-residual-plot'),
                                label="Show previous 50000 points",
                                transition='scale-x',
                                transitionDuration=300,
                                withArrow=True,
                                arrowSize=6,
                            ),
                            dmc.Tooltip(
                                dmc.Button("Next", variant="outline", id='show-next-residual-plot'),
                                label="Show next 50000 points",
                                transition='scale-x',
                                transitionDuration=300,
                                withArrow=True,
                            )
                        ],
                        className='show-div',
                        position='right',
                        id='residual-plot-nex-prev-btn-group'
                    ),

                    html.Br(),
                ],
                    loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                    className='plot-layout-full-stretch',
                    id={'type': 'plotly', 'location': 'residual', 'idx': 'residuals-plot'}
                ),
                html.Br(),
                dmc.LoadingOverlay(
                    html.Div(id='datasets-container-plot', style={'flex': 'auto', 'alignItems': 'center'},
                             children=dcc.Graph(figure=map_box)),
                    loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                    className='plot-layout-full-stretch',
                    id={'type': 'plotly', 'location': 'residual', 'idx': 'open-map-plot'}
                ),
            ],
            id='multi-plot-layout-flex',
            style={
                'display': 'flex',
                'flexWrap': 'wrap',
                'flexDirection': 'column'
                #    Responsible for creating the grids
            },
            className='two-per-row'
        ),
        html.Div(children=[
            dmc.Group(children=[
                dmc.Button('Previous', variant='outline', color='blue',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
                               'prev': 'mag_data_diurnal', 'action': 'previous'}
                           ),
                dmc.Button('Skip', variant='outline', color='gray',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
                               'prev': 'mag_data_diurnal', 'action': 'skip'}, disabled=True
                           ),
                dmc.Button('Next', variant='color', color='green',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
                               'prev': 'mag_data_diurnal', 'action': 'next'}, disabled=True),
            ])
        ],
            className='fix-bottom-right')

    ],
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'width': '100%'
        },
    )

    return mag_data_page


@callback(
    Output('mag-data-tags-div', 'children'),
    Output('select-dataset-div', 'className', allow_duplicate=True),
    Input('dropdown-dataset', 'value'),
    State('mag-data-tags-div', 'children'),
    State('local', 'data'),
    prevent_initial_call=True
)
def update_tags(selected_dataset, current_tags, session_store):
    if selected_dataset is not None:

        active_project = ProjectService.get_project_by_id(project_id=session['current_active_project'],
                                                          session=session_store)

        active_project.tags['Stage'] = 'Residual'
        active_project.tags['Survey'] = selected_dataset

        tag_buttons = generate_tag_badges(active_project, session_store, skip_extra_styling=True)

        return tag_buttons, "hide-div"
    else:
        return no_update, no_update


def generate_tag_badges(active_project, session_store, skip_extra_styling=False):
    tag_buttons = []
    idx = 0
    for key, value in active_project.tags.items():

        if skip_extra_styling:
            btn_id = f'disabled-tag-btn-{idx}'
            btn_variant = 'subtle'
            btn_color = 'gray'
        else:
            if key == 'Survey':
                btn_id = {'type': 'button',
                          'subset': 'residual-dataset-page',
                          'idx': 'select-survey-dataset',
                          'action': 'select-dataset'}
                btn_variant = 'subtle' if key not in ['Survey', 'Observatory'] else 'outline'
                btn_color = 'gray' if key not in ['Survey', 'Observatory'] else 'orange'
            elif key == 'Observatory':
                btn_id = {'type': 'button',
                          'subset': 'residual-dataset-page',
                          'idx': 'select-observatory-dataset',
                          'action': 'select-dataset'}
                btn_variant = 'subtle' if key not in ['Survey', 'Observatory'] else 'outline'
                btn_color = 'gray' if key not in ['Survey', 'Observatory'] else 'orange'
            else:
                btn_id = f'disabled-tag-btn-{idx}'
                btn_variant = 'subtle'
                btn_color = 'gray'

        btn_to_add = dmc.Group([dmc.Button(
            [
                f"{key.upper()}: ",
                dmc.Badge(f"{value}", color="secondary", className="ms-1", variant='gradient',
                          gradient={"from": "indigo", "to": "cyan"}),
            ],
            style={'display': 'inline-block', 'margin': '10px', 'padding': '5px'}, variant=btn_variant,
            color=btn_color,
            id=btn_id
        )
        ])

        idx += 1
        tag_buttons.append(btn_to_add)
    return tag_buttons


@callback(
    Output('datasets-container-plot', 'children'),
    Output('datasets-residuals-plot', 'children'),
    Output('residual-plot-nex-prev-btn-group', 'className'),
    Output('show-residuals-div', 'className'),
    Output('smoothing-constant-div', 'className'),
    Output('clip-min', 'value'),
    Output('clip-max', 'value'),
    Output('local', 'data', allow_duplicate=True),
    Input('show-previous-residual-plot', 'n_clicks'),
    Input('show-next-residual-plot', 'n_clicks'),
    Input('calc-residuals-btn', 'n_clicks'),
    Input('show-residuals-switch', 'checked'),
    Input('clip-button', 'n_clicks'),
    Input('reset-clp-btn', 'n_clicks'),
    State('ambient-smoothing-slider', 'value'),
    State('observed-smoothing-slider', 'value'),
    State('clip-min', 'value'),
    State('clip-max', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def plot_dataset(previous_button, next_button, calc_residual_btn, show_residuals, clip,
                 reset_clip, ambient, observed,
                 min_val, max_val, local_storage):
    if AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET not in session:
        session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = 0

    ct = callback_context
    triggered = ct.triggered_id

    if triggered and (previous_button is None and next_button is None and calc_residual_btn is None
                      and clip is None
                      and reset_clip is None
    ):
        raise PreventUpdate

    if 'LAST_CLICKED' not in session:
        session['LAST_CLICKED'] = 'NONE'

    dataset_id = session[AppConfig.WORKING_DATASET]

    t_start = time.time()
    df: pd.DataFrame = get_or_download_dataframe(session_store=session, dataset_id=dataset_id)

    min_mag = df['Magnetic_Field'].quantile(0.10)
    max_mag = df['Magnetic_Field'].quantile(0.90)

    min_mag_ret = min_mag if triggered == "reset-clp-btn" and reset_clip else no_update
    max_mag_ret = max_mag if triggered == "reset-clp-btn" and reset_clip else no_update

    session_store_patch = Patch() if AppConfig.POINTS_TO_CLIP in local_storage else no_update

    if AppConfig.POINTS_TO_CLIP in local_storage and triggered != 'reset-clp-btn':
        if len(local_storage[AppConfig.POINTS_TO_CLIP]) > 0:
            df.loc[np.array(local_storage[AppConfig.POINTS_TO_CLIP]).min():np.array(
                local_storage[AppConfig.POINTS_TO_CLIP]).max() + 1, 'Magnetic_Field'] = np.nan

            df['Magnetic_Field'] = df['Magnetic_Field'].interpolate(method='linear')
            # cache.delete_memoized(ResidualService.ResidualService.calculate_residuals)
            # cache.delete_memoized(MapboxScatterPlot.get_mapbox_plot)

    if triggered == "reset-clp-btn":
        cache.delete_memoized(ResidualService.ResidualService.calculate_residuals)
        cache.delete_memoized(MapboxScatterPlot.get_mapbox_plot)
        if AppConfig.POINTS_TO_CLIP in local_storage:
            del session_store_patch[AppConfig.POINTS_TO_CLIP]
        session['LAST_CLICKED'] = 'RESET_CLIP'

    if triggered == 'clip-button' and clip:
        session['LAST_CLICKED'] = 'CLIP'

    condition = min_val and max_val and min_val != "" and max_val != "" \
                and not max_mag <= float(min_val) \
                and not min_mag >= float(max_val) \
                and not (triggered == 'reset-clp-btn' and reset_clip) \
                and clip and session['LAST_CLICKED'] != 'RESET_CLIP'

    if condition:
        df['Magnetic_Field'] = df['Magnetic_Field'].mask(df['Magnetic_Field'].le(float(min_val)))

        df['Magnetic_Field'] = df['Magnetic_Field'].mask(df['Magnetic_Field'].ge(float(max_val)))

        df['Magnetic_Field'] = df['Magnetic_Field'].interpolate(method='linear')

        # cache.delete_memoized(ResidualService.ResidualService.calculate_residuals)
        # cache.delete_memoized(MapboxScatterPlot.get_mapbox_plot)

    if triggered == 'calc-residuals-btn' or 'clip-button' or calc_residual_btn is not None:
        if triggered == 'clip-button' and not condition and clip:
            return no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update

        points_to_clip = local_storage[AppConfig.POINTS_TO_CLIP] if AppConfig.POINTS_TO_CLIP in local_storage else []
        df = ResidualService.ResidualService.calculate_residuals(df, df_name=None,
                                                                 ambient_smoothing_constant=ambient,
                                                                 observed_smoothing_constant=observed,
                                                                 points_to_clip=points_to_clip,
                                                                 session_store=session)

    if not show_residuals:
        points_to_clip = local_storage[AppConfig.POINTS_TO_CLIP] if AppConfig.POINTS_TO_CLIP in local_storage else []
        fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None,
                                                col_to_plot='Magnetic_Field',
                                                points_to_clip=points_to_clip)
    else:
        points_to_clip = local_storage[AppConfig.POINTS_TO_CLIP] if AppConfig.POINTS_TO_CLIP in local_storage else []
        fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None,
                                                col_to_plot='Baseline',
                                                points_to_clip=points_to_clip
                                                )

    if triggered == 'show-next-residual-plot':
        session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = \
            min(session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] + 50000, len(df))
    elif triggered == 'show-previous-residual-plot':
        session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = \
            max(session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] - 50000, 0)

    start = int(session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET])
    end = min(start + 50000, len(df))

    custom_data = 'id' if 'id' in df.columns else None

    if not show_residuals:
        fig_residual = px.scatter(df.reset_index().iloc[start:end], x='index', y='Magnetic_Field',
                                  custom_data=custom_data,
                                  labels={
                                      "index": "Index",
                                      "Magnetic_Field": "Magnetic Field",
                                  }, title="Magnetic Field vs Recording Index"
                                  )
    else:
        fig_residual = px.scatter(df.reset_index().iloc[start:end], x='index', y='Baseline', custom_data=custom_data,
                                  labels={
                                      "index": "Index",
                                      "Baseline": "Residuals",
                                  }, title="Residuals vs Recording Index")

    if not show_residuals:
        colors = ['blue'] * 50000
    else:
        colors = df.reset_index().loc[start:end, 'Baseline']

    if 'Baseline' in df.columns and not show_residuals and triggered != 'dropdown-dataset':
        fig_residual.add_scatter(x=df.reset_index().loc[start:end, 'index'],
                                 y=df.reset_index().loc[start:end, 'Magnetic_Field_Ambient'],
                                 mode='lines', name='Ambient Smoothing')
        fig_residual.add_scatter(x=df.reset_index().loc[start:end, 'index'],
                                 y=df.reset_index().loc[start:end, 'Magnetic_Field_Smoothed'],
                                 mode='lines', name='Observed Smoothing')

    show_scale = False if not show_residuals else True
    color_scale = None if not show_residuals else 'Viridis'

    fig_residual.data[0].update(mode='lines+markers')
    fig_residual.update_layout(template='plotly_dark')
    fig_residual.update_traces(marker={'size': 2,
                                       'color': colors,
                                       'showscale': show_scale,
                                       'colorscale': color_scale})

    t_end = time.time()
    print(t_end - t_start)

    display_residuals_div = "show-div" if 'Baseline' in df.columns else no_update

    return dcc.Graph(id='map_plot', figure=fig, style={'width': '100%'}), \
        dcc.Graph(id='grap2', figure=fig_residual, style={'width': '100%'}), "show-div", display_residuals_div, \
        "show-div", min_mag_ret, max_mag_ret, session_store_patch


clientside_callback(
    """
    function(checked) {
        if (checked) {
            return "one-per-row"
        } else {
            return "two-per-row"
        }
    }
    """,
    Output("multi-plot-layout-flex", "className"),
    Input('grid-conf', "checked")
)


@callback(
    Output({'type': 'plotly', 'location': 'residual', 'idx': ALL}, "className"),
    Input('grid-conf', "checked"),
    State({'type': 'plotly', 'location': 'residual', 'idx': ALL}, "className")
)
def switch_plot_layout(checked, state):
    if checked:
        return ["plot-layout-full-stretch"] * len(state)
    else:
        return ["plot-layout-half-stretch"] * len(state)


@callback(
    Output({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
            'prev': 'mag_data_diurnal', 'action': 'skip'}, "disabled", allow_duplicate=True),
    Output({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
            'prev': 'mag_data_diurnal', 'action': 'next'}, "disabled", allow_duplicate=True),
    Input('calc-residuals-btn', 'n_clicks'),
    prevent_initial_call=True
)
def handle_next_button_state(calc_resid_clicks):
    if not calc_resid_clicks:
        return True, True
    else:
        return True, False


@callback(
    Output("tabs", "active_tab", allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
           'prev': 'mag_data_diurnal', 'action': 'next'}, "n_clicks"),
    State('observed-smoothing-slider', 'value'),
    State('ambient-smoothing-slider', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def set_data_for_interpolation_state(
        next_btn,
        observed_smoothing_constant,
        ambient_smoothing_constant,
        session_store):
    if not next_btn:
        raise PreventUpdate

    df = get_or_download_dataframe(session_store=session, dataset_id=session[AppConfig.WORKING_DATASET])

    resid_file_path = ResidualService.ResidualService\
        .calculate_residuals(df, df_name=None,
                             observed_smoothing_constant=observed_smoothing_constant,
                             ambient_smoothing_constant=ambient_smoothing_constant,
                             session_store=session,
                             purpose='save')

    new_dataset_id = str(uuid.uuid4())

    new_file_path = os.path.join(AppConfig.PROJECT_ROOT, "data",
                                 session_store[AppIDAuthProvider.APPID_USER_NAME],
                                 "downloads",
                                 f'{new_dataset_id}.csv'
                                 )

    shutil.move(src=resid_file_path, dst=new_file_path)

    parent_dataset_id = session[AppConfig.WORKING_DATASET]
    existing_dataset = DatasetService.get_dataset_by_id(parent_dataset_id,
                                                        session_store=session_store)
    project_id = session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]
    link_state = 'RESIDUALS_COMPUTED'
    tags = {'state': link_state}

    if 'Observation Dates' in existing_dataset.tags:
        tags['Observation Dates'] = existing_dataset.tags['Observation Dates']

    new_dataset: CreateNewDatasetDTO = CreateNewDatasetDTO(
        dataset=CreateDatasetDTO(
            parent_dataset_id=parent_dataset_id,
            id=new_dataset_id,
            name=existing_dataset.name,
            dataset_type_id=existing_dataset.dataset_type.id,
            project_id=project_id,
            path=f"datasets/{session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID]}/{new_dataset_id}.csv",
            tags=tags
        ),
        project_dataset_state=link_state
    )

    try:
        azr_path = '{}.csv'.format(new_dataset_id)
        created_dataset = DatasetService.create_new_dataset(dataset=new_dataset, session=session_store)

        uploader_thread = threading.Thread(
            target=BlobConnector.upload_blob, kwargs={
                'blob_name': azr_path,
                'user_id': session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID],
                'local_file_path': new_file_path,
                'linked': False
            })
        uploader_thread.start()

        # BlobConnector.upload_blob(blob_name=azr_path,
        #                           local_file_path=new_file_path,
        #                           linked=False,
        #                           user_id=session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID])

        cache.delete_memoized(DatasetService.get_dataset_by_id)
        cache.delete_memoized(ProjectService.get_project_by_id)

        session[AppConfig.WORKING_DATASET] = new_dataset_id
        return "mag_data_interpolation"
    except:
        pass


@callback(
    Output("clip-side-panel", "disabled"),
    Output("side-panel-clip-color", "color"),
    Output("local", "data", allow_duplicate=True),
    Input("grap2", "selectedData"),
    State("local", "data"),
    prevent_initial_call=True
)
def manage_sidebar_button_state(selected_data, local_storage):
    if selected_data and len(selected_data['points']) > 0:
        points_to_clip = [sd['x'] for sd in selected_data['points']]
        patch = Patch()
        if AppConfig.POINTS_TO_CLIP not in local_storage:
            patch[AppConfig.POINTS_TO_CLIP] = points_to_clip
        else:
            patch[AppConfig.POINTS_TO_CLIP].extend(points_to_clip)
        session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = points_to_clip[0]

        return False, "red", patch
    else:
        return True, "gray", no_update


@callback(
    Output('calc-residuals-btn', 'n_clicks'),
    Input('clip-side-panel', 'n_clicks'),
    State('calc-residuals-btn', 'n_clicks'),
    State('local', 'data'),
    prevent_initial_call=True
)
def clip_points(clip_btn, existing_clicks, session_store):
    existing_clicks = existing_clicks or 0
    if clip_btn and AppConfig.POINTS_TO_CLIP in session_store and len(session_store[AppConfig.POINTS_TO_CLIP]) > 0:
        return existing_clicks + 1
    else:
        return no_update


@callback(
    Output("grap2", "figure", allow_duplicate=True),
    Output("jump-plot-side-panel", "disabled"),
    Output("side-panel-jump-color", "color"),
    Input("map_plot", "selectedData"),
    prevent_initial_call=True
)
def manage_sidebar_button_state(selected_data):
    if selected_data and len(selected_data) > 0:
        return no_update, False, "cyan"
    else:
        patch = Patch()
        patch['layout']['annotations'].clear()
        return patch, True, "gray"


@callback(
    Output("grap2", "figure", allow_duplicate=True),
    Input("jump-plot-side-panel", "n_clicks"),
    State("map_plot", "selectedData"),
    State('observed-smoothing-slider', 'value'),
    State('ambient-smoothing-slider', 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def print_selected_data(btn_clicked, selected_data, observed_smoothing, ambient_smoothing, local_storage):
    if selected_data and len(selected_data) > 0 and btn_clicked:
        mod_dict = {sd['customdata'][0]: sd['customdata'][1] for sd in selected_data['points']}
        sorted_dict = sorted(mod_dict.items(), key=lambda x: abs(x[1]), reverse=True)[0]

        df = get_or_download_dataframe(session_store=session, dataset_id=session[AppConfig.WORKING_DATASET])

        points_to_clip = local_storage[AppConfig.POINTS_TO_CLIP] if AppConfig.POINTS_TO_CLIP in local_storage else []
        df_resid = ResidualService.ResidualService.calculate_residuals(df, None,
                                                                       observed_smoothing_constant=observed_smoothing,
                                                                       ambient_smoothing_constant=ambient_smoothing,
                                                                       points_to_clip=points_to_clip,
                                                                       session_store=session)

        min_index = max(0, sorted_dict[0] - 25000)
        max_index = min(len(df_resid), min_index + 50000)

        patch = Patch()

        data_col = 'Baseline'

        patch['data'][0]['x'] = df_resid.reset_index().loc[min_index:max_index, 'index'].to_numpy()
        patch['data'][0]['y'] = df_resid.reset_index().loc[min_index:max_index, data_col].to_numpy()
        patch['data'][0]['marker']['color'] = df_resid.reset_index().loc[min_index:max_index, data_col].to_numpy()
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


@cache.memoize(timeout=50000)
def get_or_download_dataframe(session_store, dataset_id, start_idx=None, end_idx=None):
    if not dataset_id:
        dataset_id = session_store[AppConfig.WORKING_DATASET]

    project = ProjectService.get_project_by_id(
        project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
        session=session_store
    )

    dataset: DatasetResponse = [d.dataset for d in project.datasets if d.dataset.id == dataset_id][0]

    if 'local_path' in dataset.tags and dataset_id in dataset.tags['local_path']:
        if start_idx is not None and end_idx is not None:

            ret_df = pd.read_csv(dataset.tags['local_path'][dataset.id],
                                 skiprows=lambda x: x > end_idx or x < start_idx)
        else:
            ret_df = pd.read_csv(dataset.tags['local_path'][dataset.id])

        if 'Observation Dates' not in dataset.tags:
            ret_df['Datetime'] = pd.to_datetime(ret_df['Datetime'])

            min_date = ret_df['Datetime'].min().strftime("%m/%d/%Y")
            max_date = ret_df['Datetime'].max().strftime("%m/%d/%Y")

            dataset_tags = dataset.tags or {}
            dataset_tags['Observation Dates'] = f'{min_date} - {max_date}'
            DatasetService.update_dataset(dataset_id=dataset.id,
                                          session_store=session_store,
                                          dataset_update_dto=DatasetUpdateDTO(tags=dataset_tags))

        if 'Magnetic_Field_Corrected' in ret_df.columns:
            ret_df['Magnetic_Field'] = ret_df['Magnetic_Field_Corrected']

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

    if start_idx is not None and end_idx is not None:
        ret_df = pd.read_csv(download_path, skiprows=lambda x: x > end_idx or x < start_idx)
    else:
        ret_df = pd.read_csv(download_path)

    if 'Observation Dates' not in updated_dataset.tags:
        ret_df['Datetime'] = pd.to_datetime(ret_df['Datetime'])

        min_date = ret_df['Datetime'].min().strftime("%m/%d/%Y")
        max_date = ret_df['Datetime'].max().strftime("%m/%d/%Y")

        dataset_tags = updated_dataset.tags or {}
        dataset_tags['Observation Dates'] = f'{min_date} - {max_date}'
        DatasetService.update_dataset(dataset_id=dataset.id,
                                      session_store=session_store,
                                      dataset_update_dto=DatasetUpdateDTO(tags=dataset_tags))

    if 'Magnetic_Field_Corrected' in ret_df.columns:
        ret_df['Magnetic_Field'] = ret_df['Magnetic_Field_Corrected']

    return ret_df


@cache.memoize(timeout=5000)
def get_residual_scatter_plot(session_store, col_to_plot):
    df_id = session_store[AppConfig.WORKING_DATASET]

    df = get_or_download_dataframe(dataset_id=df_id, session_store=session_store)
    fig_mapbox = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None,
                                                   col_to_plot=col_to_plot,
                                                   points_to_clip=[])

    start = int(session_store[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET]) \
        if AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET in session_store else 0
    end = min(start + 50000, len(df))

    custom_data = 'id' if 'id' in df.columns else None

    fig_residual = px.scatter(df.reset_index().iloc[start:end], x='index', y=col_to_plot, custom_data=custom_data,
                              labels={
                                  "index": "Index",
                                  col_to_plot: col_to_plot.replace('_', ' '),
                              }, title="Magnetic Field vs Recording Index"
                              )
    colors = ['blue'] * 50000

    fig_residual.data[0].update(mode='lines+markers')
    fig_residual.update_layout(template='plotly_dark')
    fig_residual.update_traces(marker={'size': 2, 'color': colors})

    dcc.Graph(id='map_plot', figure=fig_mapbox, style={'width': '100%'})

    return df, fig_residual, fig_mapbox


clientside_callback(
    """
    function(min_val, max_val) {
        if ( isNaN(min_val) | isNaN(max_val) | min_val === "" | max_val === "" ) {
            return true;
        } else {
            if (parseFloat(min_val) > parseFloat(max_val)) {
                return true;
            } else {
                return false;
            }
        }
    }
    """,
    Output('clip-button', 'disabled'),
    Input('clip-min', 'value'),
    Input('clip-max', 'value')
)
