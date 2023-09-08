import datetime
import time
import os.path

import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
from dash import dcc, Patch, MATCH, ALL
from dash import html, no_update, callback, callback_context, Output, Input, State
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from flask import session

from FlaskCache import cache
from api.DatasetService import DatasetService
from api.ProjectsService import ProjectService
from api.ResidualService import ResidualService
from api.dto import ProjectsOutput, UpdateProjectTagsDTO, DatasetResponse
from auth import AppIDAuthProvider
from components import ResidualComponent, MapboxScatterPlot
from utils.ExportUtils import ExportUtils


def get_datasets(typ, session_store):
    project_id = session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]
    project: ProjectsOutput = ProjectService.get_project_by_id(project_id=project_id, session=session_store)
    return [{'label': o.dataset.name, 'value': o.dataset.id} for o in project.datasets if
            o.dataset.dataset_type.name == typ]


def get_diurnal_correction_page(session_store):
    active_project = ProjectService.get_project_by_id(session=session_store,
                                                      project_id=session_store[
                                                          AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    diurnal_page = dmc.Stack([
        html.Div(ResidualComponent.get_page_tags(active_project, tags_to_add={
            'Stage': 'Diurnal Correction'
        }, session_store=session_store), id='diurnal-page-tags-div',
                 style={
                     'display': 'flex',
                     'flexDirection': 'row',
                     'flexWrap': 'wrap',
                     'alignItems': 'space-between',
                     'justifyContent': 'flex-start'
                 }),

        dmc.Group([
            dmc.Select(
                placeholder='Select Survey Data',
                label='Survey Data',
                persistence=False,
                allowDeselect=True,
                data=get_datasets(typ='SURVEY_DATA', session_store=session_store),
                icon=DashIconify(icon="arcticons:networksurvey", width=20),
                id='select-survey-data', className='show-div-simple'),
            dmc.Select(
                placeholder='Select Observatory Data',
                label='Observatory Data',
                persistence=False,
                allowDeselect=True,
                data=get_datasets(typ='OBSERVATORY_DATA', session_store=session_store),
                icon=DashIconify(icon="game-icons:observatory", width=20),
                id='select-observatory-data', className='show-div-simple'),

        ], grow=True),

        html.Div(id='durn-show-observatory_data'),

        # dmc.LoadingOverlay(children=
        # [
        #     html.Div(id='datasets-residuals-plot-durn', style={'flex': 'auto'},
        #              children=dmc.Stack(
        #                  spacing="xs",
        #                  children=[
        #                      dmc.Skeleton(height=40, width="100%", visible=False),
        #                      dmc.Skeleton(height=20, width="100%", visible=True),
        #                      dmc.Skeleton(
        #                          visible=False,
        #                          children=html.Div(id="skeleton-graph-container-durn",
        #                                            children=html.Div("PLEASE SELECT A DATASET FOR THE PLOT")),
        #                          mb=10,
        #                      ),
        #                      dmc.Skeleton(height=20, width="100%", visible=True)
        #                  ],
        #              )
        #              ),
        #     html.Br(),
        #     dmc.Group(
        #         [
        #             dmc.Tooltip(
        #                 dmc.Button("Previous", variant="outline", id='show-previous-residual-plot-durn'),
        #                 label="Show previous 50000 points",
        #                 transition='scale-x',
        #                 transitionDuration=300,
        #                 withArrow=True,
        #                 arrowSize=6,
        #             ),
        #             dmc.Tooltip(
        #                 dmc.Button("Next", variant="outline", id='show-next-residual-plot-durn'),
        #                 label="Show next 50000 points",
        #                 transition='scale-x',
        #                 transitionDuration=300,
        #                 withArrow=True,
        #             )
        #         ],
        #         className='hide-div',
        #         position='right',
        #         id='residual-plot-nex-prev-btn-group-durn'
        #     ),
        #
        #     html.Br(),
        # ],
        #     loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
        #     className='plot-layout-full-stretch',
        #     id={'type': 'plotly', 'location': 'residual', 'idx': 'residuals-plot-durn'}
        # ),

        html.Div(children=[
            dmc.Group(children=[
                dmc.Button('Skip', variant='outline', color='gray',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
                               'prev': 'None', 'action': 'skip'}),
                dmc.Button('Next', variant='color', color='green',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
                               'prev': 'None', 'action': 'next'}),
            ])
        ],
            className='fix-bottom-right')], align='stretch')

    return diurnal_page


@cache.memoize(timeout=5000)
def get_or_download_dataframe(project: ProjectsOutput, session_store, dataset_type):
    dataset: DatasetResponse = [d.dataset for d in project.datasets if d.dataset.dataset_type.name == dataset_type][0]

    if project.settings and 'local_path' in project.settings and dataset.id in project.settings['local_path']:
        return pd.read_csv(project.settings['local_path'][dataset.id])

    download_path = ExportUtils.download_data_if_not_exists(dataset_path=dataset.path,
                                                            dataset_id=dataset.id,
                                                            session=session_store)

    project_settings = project.settings or {}
    project_settings['local_path'] = {f'{dataset.id}': download_path}

    ProjectService.update_project_tags(project_tags=UpdateProjectTagsDTO(tags=project.tags, settings=project_settings),
                                       session=session_store,
                                       project_id=project.id)

    return pd.read_csv(download_path)


def get_observatory_plot(session_store):
    project = ProjectService.get_project_by_id(session=session_store,
                                               project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    df = get_or_download_dataframe(project, session_store, dataset_type='OBSERVATORY_DATA')
    return dmc.Stack(
        children=[
            dmc.Center(
                dmc.Text("Observatory Plot",
                         variant="gradient",
                         gradient={"from": "red", "to": "yellow", "deg": 45},
                         style={"fontSize": 20})),

            dmc.Center(
                dmc.Group(children=[
                    dmc.DatePicker(
                        id={'type': 'datepicker', 'idx': "observatory-data-upload-date-picker-durn"},
                        label="Observation Date",
                        # disabledDates=df['Date'].unique(),
                        description="Provide the observation date that you want to plot",
                        minDate=pd.to_datetime(df['Datetime'].min(), format='%Y-%m-%d %H:%M:%S').date(),
                        maxDate=pd.to_datetime(df['Datetime'].max(), format='%Y-%m-%d %H:%M:%S').date(),
                        placeholder='Select a Date',
                        clearable=True,
                        value=pd.to_datetime(df['Datetime'].min()).date(),
                        dropdownType="modal",
                        style={"maxWidth": '50%'},
                    ),
                    dmc.Select(
                        id={'type': 'select', 'idx': 'observatory-data-upload-dropdown-durn'},
                        label='Plot Type',
                        description='Choose either to plot the Residuals or the Raw Total Field',
                        data=['Daily Residual', 'Raw Magnetic Field'],
                        value='Raw Magnetic Field',
                        required=False,
                        searchable=False,
                        clearable=False
                    )
                ])),

            dmc.LoadingOverlay(
                dcc.Graph(id={'type': 'plotly-plot', 'idx': 'data-upload-summary-obs-plot-durn'},
                          style={'width': '100%'}),
                loaderProps={"variant": "dots", "color": "orange", "size": "xl"}
            )
        ], align='stretch')


@callback(
    Output("diurnal-page-tags-div", "children"),
    Output("select-survey-data", "className"),
    Output("select-observatory-data", "className"),
    Output("durn-show-observatory_data", "children"),
    Input("select-survey-data", "value"),
    Input("select-observatory-data", "value"),
    State("local", "data"),
    prevent_initial_call=True
)
def update_tags(survey_data, observatory_data, session_store):
    triggered = callback_context.triggered_id

    if not triggered:
        raise PreventUpdate
    elif triggered == 'select-survey-data' and not survey_data:
        raise PreventUpdate
    elif triggered == 'select-observatory-data' and not observatory_data:
        raise PreventUpdate
    else:

        if triggered == 'select-survey-data':
            survey_data = DatasetService.get_dataset_by_id(dataset_id=survey_data, session_store=session_store)

            update_tags_dto = UpdateProjectTagsDTO(tags={
                'Stage': 'Diurnal Correction',
                'Survey': survey_data.name
            })

            active_project = ProjectService.update_project_tags(session=session_store,
                                                                project_id=session_store[
                                                                    AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
                                                                project_tags=update_tags_dto)

            tags = ResidualComponent.get_page_tags(active_project, session_store=session_store)

            hide_div = True if observatory_data and survey_data else False

            if hide_div:
                ret_val = tags, "hide-div-simple", "hide-div-simple", get_observatory_plot(session_store=session_store)
            else:
                ret_val = tags, no_update, no_update, no_update
            return ret_val
        else:
            observatory_data = DatasetService.get_dataset_by_id(dataset_id=observatory_data,
                                                                session_store=session_store)

            update_tags_dto = UpdateProjectTagsDTO(tags={
                'Stage': 'Diurnal Correction',
                'Observatory': observatory_data.name
            })
            active_project = ProjectService.update_project_tags(session=session_store,
                                                                project_id=session_store[
                                                                    AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
                                                                project_tags=update_tags_dto)

            tags = ResidualComponent.get_page_tags(active_project, session_store=session_store)
            hide_div = True if observatory_data and survey_data else False

            if hide_div:
                ret_val = tags, "hide-div-simple", "hide-div-simple", get_observatory_plot(session_store=session_store)
            else:
                ret_val = tags, no_update, no_update, no_update

            return ret_val


@callback(
    Output({'type': 'plotly-plot', 'idx': 'data-upload-summary-obs-plot-durn'}, 'figure'),
    Input({'type': 'datepicker', 'idx': "observatory-data-upload-date-picker-durn"}, 'value'),
    Input({'type': 'select', 'idx': 'observatory-data-upload-dropdown-durn'}, 'value'),
    State('local', 'data')
)
def get_observatory_plot_callback(date_val, input_select, session_store):
    print(date_val)
    saved_path = os.getcwd() + f"\\data\\{session_store[AppIDAuthProvider.APPID_USER_NAME]}\\processed"

    active_project = ProjectService.get_project_by_id(session=session_store,
                                                      project_id=session_store[
                                                          AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    df = get_or_download_dataframe(session_store=session_store, project=active_project,
                                   dataset_type='OBSERVATORY_DATA')
    plot_df = df

    min_date = date_val
    max_date = (pd.to_datetime(date_val, format='%Y-%m-%d') + datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    plot_df = plot_df[(plot_df['Datetime'] >= min_date) & (plot_df['Datetime'] < max_date)]

    y_plot = 'Magnetic_Field' if input_select == 'Raw Magnetic Field' else 'Baseline'

    obs_plot = px.line(plot_df, x='Datetime', y=y_plot, hover_data={"Datetime": "|%B %d, %Y %I:%M"})
    obs_plot.update_layout(hovermode='x unified')
    obs_plot.update_layout(template='plotly_dark')

    return obs_plot


@callback(
    Output("select-survey-data", "className", allow_duplicate=True),
    Output("select-observatory-data", "className", allow_duplicate=True),
    Input({'type': 'button', 'subset': 'residual-dataset-page', 'idx': ALL, 'action': ALL}, 'n_clicks'),
    State("select-survey-data", 'className'),
    State("select-observatory-data", 'className'),
    prevent_initial_call=True
)
def hide_dataset_selection_div(n_clicks, survey_state, observatory_state):
    ct = callback_context
    button_id = ct.triggered_id
    if button_id['idx'] == 'select-survey-dataset':
        if n_clicks[0]:
            return "show-div-simple" if survey_state == "hide-div-simple" else "hide-div-simple", no_update
        else:
            return no_update, no_update
    elif button_id['idx'] == 'select-observatory-dataset':
        if n_clicks[1]:
            return no_update, "show-div-simple" if observatory_state == "hide-div-simple" else "hide-div-simple"
        else:
            return no_update, no_update
    else:
        raise PreventUpdate


# @callback(
#     Output('datasets-residuals-plot-durn', 'children'),
#     Output('residual-plot-nex-prev-btn-group-durn', 'className'),
#     Input('show-previous-residual-plot-durn', 'n_clicks'),
#     Input('show-next-residual-plot-durn', 'n_clicks'),
#     Input('show-residuals-switch-durn', 'checked'),
#     State('local', 'session-store'),
#     prevent_initial_call=True
# )
# def plot_dataset(previous_button, next_button, show_residuals, session_store):
#     if AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET not in session:
#         session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = 0
#
#     ct = callback_context
#     triggered = ct.triggered_id
#
#     active_project = ProjectService.get_project_by_id(session=session_store,
#                                                       project_id=session_store[
#                                                           AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])
#
#     obs_df = get_or_download_dataframe(session_store=session_store, project=active_project,
#                                        dataset_type='OBSERVATORY_DATA')
#
#     surf_df = get_or_download_dataframe(session_store=session_store, project=active_project,
#                                         dataset_type='OBSERVATORY_DATA')
#
#
#     surf_df_durn_computed = ResidualService.calculate_residuals(df, df_name=selected_dataset,
#                                              ambient_smoothing_constant=ambient,
#                                              observed_smoothing_constant=observed)
#
#     if not show_residuals:
#         fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=selected_dataset, col_to_plot='Magnetic_Field')
#     else:
#         fig = MapboxScatterPlot.get_mapbox_plot(df=df, df_name=selected_dataset, col_to_plot='Baseline')
#
#         if triggered == 'show-next-residual-plot':
#             session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = \
#                 min(session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] + 50000, len(df))
#         elif triggered == 'show-previous-residual-plot':
#             session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] = \
#                 max(session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET] - 50000, 0)
#
#         start = int(session[AppIDAuthProvider.PLOTLY_SCATTER_PLOT_SUBSET])
#         end = min(start + 50000, len(df))
#
#         custom_data = 'id' if 'id' in df.columns else None
#
#         if not show_residuals:
#             fig_residual = px.scatter(df.iloc[start:end], x='Unnamed: 0', y='Magnetic_Field', custom_data=custom_data,
#                                       labels={
#                                           "Unnamed: 0": "Index",
#                                           "Magnetic_Field": "Magnetic Field",
#                                       }, title="Magnetic Field vs Recording Index"
#                                       )
#         else:
#             fig_residual = px.scatter(df.iloc[start:end], x='Unnamed: 0', y='Baseline', custom_data=custom_data,
#                                       labels={
#                                           "Unnamed: 0": "Index",
#                                           "Baseline": "Residuals",
#                                       }, title="Residuals vs Recording Index")
#
#         colors = ['blue'] * 50000
#
#         fig_residual.data[0].update(mode='lines+markers')
#         fig_residual.update_layout(template='plotly_dark')
#         fig_residual.update_traces(marker={'size': 2, 'color': colors})
#
#         t_end = time.time()
#         print(t_end - t_start)
#
#         display_residuals_div = "show-div" if 'Baseline' in df.columns else no_update
#
#         return dcc.Graph(id='map_plot', figure=fig, style={'width': '100%'}), \
#             dcc.Graph(id='grap2', figure=fig_residual, style={'width': '100%'}), "show-div", display_residuals_div, \
#             "show-div"
#     else:
#         return no_update, no_update, no_update, no_update, "show-div"
