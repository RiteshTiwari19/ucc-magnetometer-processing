import time

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
import numpy as np
import plotly.express as px
from dash import dcc, html, Input, Output, State, Patch, no_update, ALL, callback, clientside_callback, \
    callback_context, MATCH
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from flask import session

from FlaskCache import cache
from api import ResidualService
from api.ProjectsService import ProjectService
from api.dto import UpdateProjectTagsDTO
from auth import AppIDAuthProvider
from components import ModalComponent, MapboxScatterPlot
from dataservices import InMermoryDataService


def get_page_tags(active_project, tags_to_add: dict = None):
    if tags_to_add:
        for k, v in tags_to_add.items():
            active_project.tags[k] = v

    tag_buttons = [dmc.Group([dmc.Button(
        [
            f"{key.upper()}: ",
            dmc.Badge(f"{value}", color="secondary", className="ms-1", variant='gradient',
                      gradient={"from": "indigo", "to": "cyan"}),
        ],
        style={'display': 'inline-block', 'margin': '10px', 'padding': '5px'}, variant='subtle', color='gray'
    )
    ]) for key, value in active_project.tags.items()]

    return tag_buttons


def get_mag_data_page(session, configured_du):
    active_project = ProjectService.get_project_by_id(project_id=session['current_active_project'],
                                                      session=session)
    active_session = session[AppIDAuthProvider.APPID_USER_NAME]
    datasets = InMermoryDataService.DatasetsService.get_existing_datasets()
    drop_down_options = [{'label': dataset.name, 'value': dataset.name} for dataset in datasets]

    mag_data_page = html.Div([
        html.Div(ModalComponent.get_upload_data_modal(configured_du,
                                                      upload_id=session[AppIDAuthProvider.APPID_USER_NAME]),
                 style={'width': '100%'}),
        html.Div(get_page_tags(active_project, tags_to_add={
            'Stage': 'Residual'
        }), id='mag-data-tags-div',
                 style={
                     'display': 'flex',
                     'flexDirection': 'row',
                     'flexWrap': 'wrap',
                     'alignItems': 'space-between',
                     'justifyContent': 'flex-start'
                 }),
        html.Div(id="selected-data-div"),
        html.Div([
            html.Span('Please', style={'marginRight': '1.5rem'}),
            dmc.Select(
                data=drop_down_options,
                id='dropdown-dataset',
                searchable=True,
                nothingFound="No dataset found",
                icon=DashIconify(icon="bxs:data"),
                persistence=True,
                placeholder='Select Dataset',
                selectOnBlur=True,
                clearable=True,
                required=True
            ),

            html.Span('an existing dataset', style={'marginLeft': '1.5rem'}),
            html.Div(dbc.Badge('OR', color="secondary", text_color="white",
                               className="ms-1"), style={'marginLeft': '1.5rem'}),

            dbc.Button("Upload", color="primary", style={'marginLeft': '1.5rem'},
                       id={'type': 'button', 'subset': 'modal', 'action': 'open', 'idx': 'open-upload-modal'}),
            html.Span('a new one', style={'marginLeft': '1.5rem'}),
        ],
            style={
                'display': 'flex',
                'flexDirection': 'row',
                'flexWrap': 'wrap',
                'alignItems': 'center',
                'justifyContent': 'center'
            }, id='select-dataset-div'
        ),
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
                                     dmc.Skeleton(height=40, width="100%", visible=False),
                                     dmc.Skeleton(height=20, width="100%", visible=True),
                                     dmc.Skeleton(
                                         visible=False,
                                         children=html.Div(id="skeleton-graph-container",
                                                           children=html.Div("PLEASE SELECT A DATASET FOR THE PLOT")),
                                         mb=10,
                                     ),
                                     dmc.Skeleton(height=20, width="100%", visible=True)
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
                        className='hide-div',
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
                             children=[
                                 dmc.Stack(
                                     spacing="xs",
                                     children=[
                                         dmc.Skeleton(height=40, width="100%", visible=False),
                                         dmc.Skeleton(height=20, width="100%", visible=True),
                                         dmc.Skeleton(
                                             visible=False,
                                             children=html.Div(id="skeleton-graph-container",
                                                               children=html.Div(
                                                                   "PLEASE SELECT A DATASET FOR THE PLOT")),
                                             mb=10,
                                         ),
                                         dmc.Skeleton(height=20, width="100%", visible=True)
                                     ],
                                 )
                             ]),
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

        tag_buttons = []
        idx = 0
        for key, value in active_project.tags.items():
            btn_id = f'disabled-tag-btn-{idx}' if key != 'Survey' else {'type': 'button',
                                                                        'subset': 'residual-dataset-page',
                                                                        'idx': 'select-dataset',
                                                                        'action': 'select-dataset'}
            btn_variant = 'subtle' if key != 'Survey' else 'outline'
            btn_color = 'gray' if key != 'Survey' else 'orange'

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

        return tag_buttons, "hide-div"
    else:
        return no_update, no_update


def hide_dataset_selection_div_outer(app: dash.Dash):
    @app.callback(
        Output("select-dataset-div", "className", allow_duplicate=True),
        Output('dropdown-dataset', 'value', allow_duplicate=True),
        Input({'type': 'button', 'subset': 'residual-dataset-page', 'idx': ALL, 'action': ALL}, 'n_clicks'),
        State("select-dataset-div", "className"),
        prevent_initial_call=True
    )
    def hide_dataset_selection_div(n_clicks, current_state):
        ct = dash.callback_context
        button_id = ct.triggered_id
        if button_id['action'] == 'select-dataset':
            if n_clicks[0]:
                return "show-div" if current_state == "hide-div" else "hide-div", None
            else:
                return no_update, no_update


@callback(
    Output('datasets-container-plot', 'children'),
    Output('datasets-residuals-plot', 'children'),
    Output('residual-plot-nex-prev-btn-group', 'className'),
    Output('show-residuals-div', 'className'),
    Output('smoothing-constant-div', 'className'),
    Input('dropdown-dataset', 'value'),
    Input('show-previous-residual-plot', 'n_clicks'),
    Input('show-next-residual-plot', 'n_clicks'),
    Input('calc-residuals-btn', 'n_clicks'),
    Input('show-residuals-switch', 'checked'),  #####
    State('ambient-smoothing-slider', 'value'),
    State('observed-smoothing-slider', 'value'),
    prevent_initial_call=True
)
def plot_dataset(selected_dataset, previous_button, next_button, calc_residual_btn, show_residuals, ambient, observed):
    if AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET not in session:
        session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = 0

    ct = callback_context
    triggered = ct.triggered_id

    if selected_dataset is not None and type(selected_dataset) == str:
        t_start = time.time()
        df = InMermoryDataService.DatasetsService.get_dataset_by_name(selected_dataset)

        if triggered == 'calc-residuals-btn' or calc_residual_btn is not None:
            df = ResidualService.ResidualService.calculate_residuals(df, df_name=selected_dataset,
                                                                     ambient_smoothing_constant=ambient,
                                                                     observed_smoothing_constant=observed)

        if not show_residuals:
            fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=selected_dataset, col_to_plot='Magnetic_Field')
        else:
            fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=selected_dataset, col_to_plot='Baseline')

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
    else:
        return no_update, no_update, no_update, no_update, "show-div"


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
