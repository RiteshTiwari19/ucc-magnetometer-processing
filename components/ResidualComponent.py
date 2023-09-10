import time

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import plotly.express as px
from dash import dcc, html, Input, Output, State, no_update, ALL, callback, clientside_callback, \
    callback_context
from dash_iconify import DashIconify
from flask import session

import AppConfig
from FlaskCache import cache
from api import ResidualService
from api.DatasetService import DatasetService
from api.ProjectsService import ProjectService
from api.dto import ProjectsOutput, DatasetResponse, DatasetUpdateDTO
from auth import AppIDAuthProvider
from components import ModalComponent, MapboxScatterPlot
from dataservices import InMermoryDataService
from flask import session

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

    scatter, map_box = get_residual_scatter_plot(session_store=session, col_to_plot='Magnetic_Field')

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

        ], spacing='lg', className='hide-div', id='smoothing-constant-div', position='center'),

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
                className='hide-div', id='show-residuals-div')
        ]),

        html.Br(),

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
                               'prev': 'mag_data_diurnal', 'action': 'skip'}
                           ),
                dmc.Button('Next', variant='color', color='green',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data_interpolation',
                               'prev': 'mag_data_diurnal', 'action': 'next'}),
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


# def hide_dataset_selection_div_outer(app: dash.Dash):
#     @app.callback(
#         Output("select-dataset-div", "className", allow_duplicate=True),
#         Output('dropdown-dataset', 'value', allow_duplicate=True),
#         Input({'type': 'button', 'subset': 'residual-dataset-page', 'idx': ALL, 'action': ALL}, 'n_clicks'),
#         State("select-dataset-div", "className"),
#         prevent_initial_call=True
#     )
#     def hide_dataset_selection_div(n_clicks, current_state):
#         ct = dash.callback_context
#         button_id = ct.triggered_id
#         if button_id['action'] == 'select-dataset':
#             if n_clicks[0]:
#                 return "show-div" if current_state == "hide-div" else "hide-div", None
#             else:
#                 return no_update, no_update


@callback(
    Output('datasets-container-plot', 'children'),
    Output('datasets-residuals-plot', 'children'),
    Output('residual-plot-nex-prev-btn-group', 'className'),
    Output('show-residuals-div', 'className'),
    Output('smoothing-constant-div', 'className'),
    Input('show-previous-residual-plot', 'n_clicks'),
    Input('show-next-residual-plot', 'n_clicks'),
    Input('calc-residuals-btn', 'n_clicks'),
    Input('show-residuals-switch', 'checked'),
    State('ambient-smoothing-slider', 'value'),
    State('observed-smoothing-slider', 'value'),
    prevent_initial_call=True
)
def plot_dataset(previous_button, next_button, calc_residual_btn, show_residuals, ambient, observed):
    if AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET not in session:
        session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = 0

    ct = callback_context
    triggered = ct.triggered_id

    dataset_id = session[AppConfig.WORKING_DATASET]

    t_start = time.time()
    df = get_or_download_dataframe(session_store=session, dataset_id=dataset_id)

    if triggered == 'calc-residuals-btn' or calc_residual_btn is not None:
        df = ResidualService.ResidualService.calculate_residuals(df, df_name=None,
                                                                 ambient_smoothing_constant=ambient,
                                                                 observed_smoothing_constant=observed)

    if not show_residuals:
        fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None, col_to_plot='Magnetic_Field')
    else:
        fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None, col_to_plot='Baseline')

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
        fig_residual = px.scatter(df.iloc[start:end], x='Unnamed: 0', y='Magnetic_Field', custom_data=custom_data,
                                  labels={
                                      "Unnamed: 0": "Index",
                                      "Magnetic_Field": "Magnetic Field",
                                  }, title="Magnetic Field vs Recording Index"
                                  )
    else:
        fig_residual = px.scatter(df.iloc[start:end], x='Unnamed: 0', y='Baseline', custom_data=custom_data,
                                  labels={
                                      "Unnamed: 0": "Index",
                                      "Baseline": "Residuals",
                                  }, title="Residuals vs Recording Index")

    if not show_residuals:
        colors = ['blue'] * 50000
    else:
        colors = ['red' if abs(i) > 3 else 'blue' for i in df.loc[start:end, 'Baseline']]

    if 'Baseline' in df.columns and not show_residuals and triggered != 'dropdown-dataset':
        fig_residual.add_scatter(x=df.loc[start:end, 'Unnamed: 0'], y=df.loc[start:end, 'Magnetic_Field_Ambient'],
                                 mode='lines', name='Ambient Smoothing')
        fig_residual.add_scatter(x=df.loc[start:end, 'Unnamed: 0'], y=df.loc[start:end, 'Magnetic_Field_Smoothed'],
                                 mode='lines', name='Observed Smoothing')

    fig_residual.data[0].update(mode='lines+markers')
    fig_residual.update_layout(template='plotly_dark')
    fig_residual.update_traces(marker={'size': 2, 'color': colors})

    t_end = time.time()
    print(t_end - t_start)

    display_residuals_div = "show-div" if 'Baseline' in df.columns else no_update

    return dcc.Graph(id='map_plot', figure=fig, style={'width': '100%'}), \
        dcc.Graph(id='grap2', figure=fig_residual, style={'width': '100%'}), "show-div", display_residuals_div, \
        "show-div"


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
    Output("tabs", "active_tab", allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'main-proj-flow', 'next': ALL,
           'prev': ALL, 'action': ALL}, "n_clicks"),
    Input("tabs", "active_tab"),
    prevent_initial_call=True
)
def switch_tab(btn_click, current_active_tab):
    prev_next_dict = {
        'mag_data_diurnal': {'prev': 'None', 'next': 'mag_data'},
        'mag_data': {'prev': 'mag_data_diurnal', 'next': 'mag_data_interpolation'},
        'mag_data_interpolation': {'prev': 'mag_data', 'next': 'None'},
    }

    if any(click for click in btn_click):
        triggered = callback_context.triggered_id

        if type(triggered) == str:
            return current_active_tab

        action = triggered['action']

        next = triggered['next']
        prev = triggered['prev']

        if action == 'next' and next == 'mag_data':
            return no_update

        if action == 'next' and next != 'None':
            if current_active_tab != prev_next_dict[next]['prev']:
                return current_active_tab
            else:
                return next
        if action == 'skip' and next != 'None':
            if current_active_tab != prev_next_dict[next]['prev']:
                return current_active_tab
            else:
                return next
        if action == 'previous' and prev != 'None':
            if current_active_tab != prev_next_dict[prev]['next']:
                return current_active_tab
            else:
                return prev
    else:
        return no_update


@callback(
    Output("selected-data-div", "children"),
    Input("grap2", "selectedData")
)
def print_selected_data(selected_data):
    print(selected_data)
    return html.Div()


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

    return ret_df


@cache.memoize(timeout=5000)
def get_residual_scatter_plot(session_store, col_to_plot):
    df_id = session_store[AppConfig.WORKING_DATASET]

    df = get_or_download_dataframe(dataset_id=df_id, session_store=session_store)
    fig_mapbox = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=None, col_to_plot=col_to_plot)

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

    return fig_residual, fig_mapbox
