import datetime
import shutil
import threading
import time
import os.path
import uuid

import dash_mantine_components as dmc
import numpy as np
import pandas as pd
import plotly.express as px
from dash import dcc, Patch, MATCH, ALL, clientside_callback
from dash import html, no_update, callback, callback_context, Output, Input, State
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify
from flask import session
import plotly.graph_objs as go

import AppConfig
from FlaskCache import cache
from api.DatasetService import DatasetService
from api.ProjectsService import ProjectService
from api.ResidualService import ResidualService
from api.dto import ProjectsOutput, UpdateProjectTagsDTO, DatasetResponse, DatasetUpdateDTO, CreateNewDatasetDTO, \
    CreateDatasetDTO
from auth import AppIDAuthProvider
from components import ResidualComponent, MapboxScatterPlot
from utils.AzureContainerHelper import BlobConnector
from utils.ExportUtils import ExportUtils


def get_datasets(typ, session_store):
    project_id = session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]
    project: ProjectsOutput = ProjectService.get_project_by_id(project_id=project_id, session=session_store)
    return [{'label': o.dataset.name, 'value': o.dataset.id} for o in project.datasets if
            o.dataset.dataset_type.name == typ and o.dataset.tags['state'] == 'LINKED' if 'state' in o.dataset.tags]


@cache.memoize(args_to_ignore=['session_store'])
def get_survey_plot(session_store, col_to_plot, dataset_id):
    start_index = session_store[
        AppConfig.SURVEY_DATA_START_IDX] if AppConfig.SURVEY_DATA_START_IDX in session_store else 0

    start = start_index
    end = start_index + 50000

    active_project = ProjectService.get_project_by_id(
        project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
        session=session_store)
    df = get_or_download_dataframe(project=active_project, session_store=session_store, dataset_type='SURVEY_DATA'
                                   , dataset_id=dataset_id)

    df = df.set_index('Datetime').sort_index().reset_index().reset_index()

    custom_data = 'index' if 'index' in df.columns else 'Datetime'

    fig_residual = px.scatter(df.iloc[start:end], x='index', y=col_to_plot, custom_data=custom_data,
                              labels={
                                  "index": "Index",
                                  "Magnetic_Field": "Magnetic Field",
                              }, title="Magnetic Field vs Recording Index"
                              )
    fig_residual.data[0].update(mode='lines+markers')
    fig_residual.update_layout(template='plotly_dark')
    fig_residual.update_traces(marker={'size': 2})

    ret_div = dmc.LoadingOverlay(children=
    [
        dmc.Center(
            dmc.Text("Survey Data",
                     variant="gradient",
                     gradient={"from": "red", "to": "yellow", "deg": 45},
                     style={"fontSize": 20})),
        html.Br(),
        html.Div(id='datasets-residuals-plot-durn-parent', style={'flex': 'auto'},
                 children=dcc.Graph(id={'type': 'plotly-plot', 'idx': 'residual-plot'}, figure=fig_residual)
                 ),
        html.Br(),
        dmc.Center(
            dmc.Button("Remove Diurnal Variation", variant="filled",
                       id={'id': 'perform-diurnal-correction', 'action': 'calc_durn'}),
        ),
        dmc.Group(
            [
                dmc.Tooltip(
                    dmc.Button("Previous", variant="outline", id='show-previous-residual-plot-durn'),
                    label="Show previous 50000 points",
                    transition='scale-x',
                    transitionDuration=300,
                    withArrow=True,
                    arrowSize=6,
                ),
                dmc.Tooltip(
                    dmc.Button("Next", variant="outline", id='show-next-residual-plot-durn'),
                    label="Show next 50000 points",
                    transition='scale-x',
                    transitionDuration=300,
                    withArrow=True,
                )
            ],
            className='show-div',
            position='right',
            id='residual-plot-nex-prev-btn-group-durn'
        ),

        html.Br(),
    ],
        loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
        className='plot-layout-full-stretch',
        id={'type': 'plotly', 'location': 'residual', 'idx': 'residuals-plot-durn'}
    ),

    return f'{df["Datetime"].min().strftime("%m/%d/%Y")} - {df["Datetime"].max().strftime("%m/%d/%Y")}', ret_div


def get_diurnal_correction_page(session_store):
    active_project = ProjectService.get_project_by_id(session=session_store,
                                                      project_id=session_store[
                                                          AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    if 'Survey' in active_project.tags:
        del active_project.tags['Survey']

    if 'Observatory' in active_project.tags:
        del active_project.tags['Observatory']

    diurnal_page = dmc.Stack([
        html.Div(id='dummy'),
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

        dmc.Divider(size=3,
                    color='gray', variant='dashed', style={'marginTop': '1em', 'marginBottom': '1.5em'}),
        dmc.Text("Select Datasets", weight=500,
                 style={"fontSize": 20, "color": "#009688"}),

        dmc.Group([
            dmc.Select(
                placeholder='Select Survey Data',
                label='Survey Data',
                persistence=False,
                allowDeselect=True,
                data=get_datasets(typ='SURVEY_DATA', session_store=session_store),
                icon=DashIconify(icon="arcticons:networksurvey", width=20),
                id='select-survey-data', className='show-div-simple'),
            dmc.MultiSelect(
                placeholder='Select Observatory Data',
                label='Observatory Data',
                persistence=False,
                debounce=2000,
                data=get_datasets(typ='OBSERVATORY_DATA', session_store=session_store),
                icon=DashIconify(icon="game-icons:observatory", width=20),
                id='select-observatory-data', className='show-div-simple'),
        ], grow=True),

        html.Div(id='durn-show-observatory_data'),
        html.Div(id='durn-show-residual-data'),

        html.Div(children=[
            dmc.Group(children=[
                dmc.Button('Skip', variant='outline', color='gray',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
                               'prev': 'None', 'action': 'skip'}, disabled=True),
                dmc.Button('Next', variant='color', color='green',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
                               'prev': 'None', 'action': 'next'}, disabled=True),
            ])
        ],
            className='fix-bottom-right')], align='stretch')

    return diurnal_page


@callback(
    Output("local", "data", allow_duplicate=True),
    Input("select-survey-data", "value"),
    Input("select-observatory-data", "value"),
    State("local", "data"),
    prevent_initial_call=True
)
def update_datasets_in_session(survey_data_selected, observatory_data_selected, store):
    if not callback_context.triggered or not (survey_data_selected or observatory_data_selected):
        raise PreventUpdate
    else:
        patch = Patch()
        if callback_context.triggered_id == 'select-survey-data':
            patch[AppConfig.SURVEY_DATA_SELECTED] = survey_data_selected
        else:
            patch[AppConfig.OBS_DATA_SELECTED] = observatory_data_selected
    return patch


@cache.memoize(timeout=50000)
def get_or_download_dataframe(project: ProjectsOutput, session_store, dataset_type,
                              dataset_id, start_idx=None, end_idx=None):
    if not dataset_id:
        dataset_id = session_store[AppConfig.SURVEY_DATA_SELECTED] if dataset_type == 'SURVEY_DATA' else session_store[
            AppConfig.OBS_DATA_SELECTED]

    dataset: DatasetResponse = [d.dataset for d in project.datasets if d.dataset.id == dataset_id][0]

    if 'local_path' in dataset.tags and dataset_id in dataset.tags['local_path'] \
            and os.path.exists(dataset.tags['local_path'][dataset.id]):
        if start_idx is not None and end_idx is not None:

            ret_df = pd.read_csv(dataset.tags['local_path'][dataset.id],
                                 skiprows=lambda x: x > end_idx or x < start_idx)
        else:
            ret_df = pd.read_csv(dataset.tags['local_path'][dataset.id])

        ret_df['Datetime'] = pd.to_datetime(ret_df['Datetime'], format='mixed')

        if 'Observation Dates' not in dataset.tags:
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
        ret_df['Datetime'] = pd.to_datetime(ret_df['Datetime'], format='mixed')

    if 'Observation Dates' not in updated_dataset.tags:
        min_date = ret_df['Datetime'].min().strftime("%m/%d/%Y")
        max_date = ret_df['Datetime'].max().strftime("%m/%d/%Y")

        dataset_tags = updated_dataset.tags or {}
        dataset_tags['Observation Dates'] = f'{min_date} - {max_date}'
        DatasetService.update_dataset(dataset_id=dataset.id,
                                      session_store=session_store,
                                      dataset_update_dto=DatasetUpdateDTO(tags=dataset_tags))

    return ret_df


@cache.memoize(timeout=5000)
def concat_dfs(dfs):
    return pd.concat(dfs)


@cache.memoize(timeout=50000, args_to_ignore=['session_store'])
def get_observatory_plot(session_store, dataset_id=None):
    project = ProjectService.get_project_by_id(session=session_store,
                                               project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])
    dfs = []
    for d_id in dataset_id:
        df = get_or_download_dataframe(project, session_store, dataset_type='OBSERVATORY_DATA', dataset_id=d_id)
        dfs.append(df)

    df = concat_dfs(dfs)

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
            ),
        ], align='stretch')


@callback(
    Output("diurnal-page-tags-div", "children"),
    Output("select-survey-data", "className"),
    Output("select-observatory-data", "className"),
    Output("durn-show-observatory_data", "children"),
    Output("durn-show-residual-data", 'children', allow_duplicate=True),
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
            cache.delete_memoized(ResidualService.calculate_diurnal_correction)
            cache.delete_memoized(perform_diurnal_correction)
            survey_data = DatasetService.get_dataset_by_id(dataset_id=survey_data, session_store=session_store)

            survey_dates, survey_plot = get_survey_plot(session_store=session_store, col_to_plot='Magnetic_Field',
                                                        dataset_id=survey_data.id)

            update_tags_dto = UpdateProjectTagsDTO(tags={
                'Stage': 'Diurnal Correction',
                'Survey': survey_data.name,
                'Survey Duration': survey_dates
            })

            active_project = update_project_tags(session_store, update_tags_dto)
            if 'Observatory' in active_project.tags and not observatory_data:
                del active_project.tags['Observatory']

            tags = ResidualComponent.get_page_tags(active_project, session_store=session_store)

            hide_div = True if observatory_data and survey_data else False

            if hide_div:
                ret_val = tags, "hide-div-simple", "hide-div-simple", no_update, survey_plot

            else:
                ret_val = tags, no_update, no_update, no_update, survey_plot
            return ret_val
        else:
            cache.delete_memoized(ResidualService.calculate_diurnal_correction)
            cache.delete_memoized(perform_diurnal_correction)

            observatory_datasets = []
            for data in observatory_data:
                observatory_datasets.append(DatasetService.get_dataset_by_id(dataset_id=data,
                                                                             session_store=session_store))

            update_tags_dto = UpdateProjectTagsDTO(tags={
                'Stage': 'Diurnal Correction',
                'Observatory': 'Multiple' if len(observatory_datasets) > 1 else observatory_datasets[0].name
            })
            active_project = update_project_tags(session_store, update_tags_dto)

            if 'Survey' in active_project.tags and not survey_data:
                del active_project.tags['Survey']

            tags = ResidualComponent.get_page_tags(active_project, session_store=session_store)

            hide_div = True if observatory_data and survey_data else False

            if hide_div:
                ret_val = tags, "hide-div-simple", "hide-div-simple", \
                    get_observatory_plot(session_store=session_store,
                                         dataset_id=[od.id for od in observatory_datasets]), no_update
            else:
                ret_val = tags, no_update, no_update, \
                    get_observatory_plot(session_store=session_store,
                                         dataset_id=[od.id for od in observatory_datasets]), no_update

            return ret_val


def update_project_tags(session_store, update_tags_dto):
    updated_project = ProjectService.update_project_tags(session=session_store,
                                                         project_id=session_store[
                                                             AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
                                                         project_tags=update_tags_dto)
    return updated_project


@callback(
    Output({'type': 'plotly-plot', 'idx': 'data-upload-summary-obs-plot-durn'}, 'figure'),
    Input({'type': 'datepicker', 'idx': "observatory-data-upload-date-picker-durn"}, 'value'),
    Input({'type': 'select', 'idx': 'observatory-data-upload-dropdown-durn'}, 'value'),
    State('local', 'data'),
    prevent_initial_call=True
)
def get_plots_callback(date_val, input_select, session_store):
    print(date_val)
    active_project = ProjectService.get_project_by_id(session=session_store,
                                                      project_id=session_store[
                                                          AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    obs_ids = session_store[AppConfig.OBS_DATA_SELECTED]
    dfs = []
    for d_id in obs_ids:
        dfs.append(get_or_download_dataframe(session_store=session_store, project=active_project,
                                             dataset_type='OBSERVATORY_DATA', dataset_id=d_id))

    df = concat_dfs(dfs)

    # df_surf_plot = get_survey_plot(session_store=session_store, col_to_plot='Magnetic_Field')
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
        clicked = n_clicks[0] if len(n_clicks) == 1 else n_clicks[1]
        if clicked:
            return "show-div-simple" if survey_state == "hide-div-simple" else "hide-div-simple", no_update
        else:
            return no_update, no_update
    elif button_id['idx'] == 'select-observatory-dataset':
        clicked = n_clicks[0] if len(n_clicks) == 1 else n_clicks[1]
        if clicked:
            return no_update, "show-div-simple" if observatory_state == "hide-div-simple" else "hide-div-simple"
        else:
            return no_update, no_update
    else:
        raise PreventUpdate


@callback(
    Output({'type': 'plotly-plot', 'idx': 'residual-plot'}, 'figure', allow_duplicate=True),
    Output('local', 'data', allow_duplicate=True),
    Output({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
            'prev': 'None', 'action': 'next'}, 'disabled', allow_duplicate=True),
    Input('show-previous-residual-plot-durn', 'n_clicks'),
    Input('show-next-residual-plot-durn', 'n_clicks'),
    Input({'id': 'perform-diurnal-correction', 'action': 'calc_durn'}, 'n_clicks'),
    State('local', 'data'),
    prevent_initial_call=True
)
def diurnal_correction_cta(
        previous_button,
        next_button,
        diurnal_correction,
        session_store):
    session_store_patch = Patch()
    if AppConfig.SURVEY_DATA_START_IDX not in session_store:
        session_store_patch[AppConfig.SURVEY_DATA_START_IDX] = 0

    ct = callback_context
    triggered = ct.triggered_id
    disable_next = False

    if not previous_button and not next_button and not diurnal_correction:
        raise PreventUpdate

    active_project = ProjectService.get_project_by_id(session=session_store,
                                                      project_id=session_store[
                                                          AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])

    if type(triggered) is not str and triggered[
        'id'] == "perform-diurnal-correction" and diurnal_correction is not None:

        surf_df_diurnal_computed = perform_diurnal_correction(active_project, session_store)
        disable_next = False

        start = int(session_store[AppConfig.SURVEY_DATA_START_IDX]) if \
            AppConfig.SURVEY_DATA_START_IDX in session_store else 0
        end = min(start + 50000, len(surf_df_diurnal_computed))
        surf_df_diurnal_computed = surf_df_diurnal_computed.iloc[start:end]

        fig = generate_line_plot(surf_df_diurnal_computed)

        session_store_patch[AppConfig.DIURNAL_COMPUTED] = True

        return fig, session_store_patch, disable_next
    elif triggered == 'show-next-residual-plot-durn' and next_button is not None:

        if diurnal_correction is not None and diurnal_correction > 0:
            surf_df_diurnal_computed = perform_diurnal_correction(active_project, session_store)

            session_store_patch[AppConfig.SURVEY_DATA_START_IDX] = start = \
                min(session_store[AppConfig.SURVEY_DATA_START_IDX] + 50000, len(surf_df_diurnal_computed)) \
                    if AppConfig.SURVEY_DATA_START_IDX in session_store else 0

            end = min(start + 50000, len(surf_df_diurnal_computed))
            surf_df_diurnal_computed = surf_df_diurnal_computed.iloc[start:end]

            fig = generate_line_plot(surf_df_diurnal_computed)

            return fig, session_store_patch, False
        else:
            session_store_patch[
                AppConfig.SURVEY_DATA_START_IDX] = start = int(session_store[AppConfig.SURVEY_DATA_START_IDX]) + 50000 \
                if AppConfig.SURVEY_DATA_START_IDX in session_store else 0
            end = start + 50000

            dataset_id = session_store[AppConfig.SURVEY_DATA_SELECTED]

            active_project = ProjectService.get_project_by_id(
                project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
                session=session_store)

            df = get_or_download_dataframe(project=active_project, session_store=session_store,
                                           dataset_type='SURVEY_DATA', dataset_id=dataset_id)

            df = df.set_index('Datetime').sort_index().reset_index().reset_index()
            df = df.iloc[start:end]

            custom_data = 'index' if 'index' in df.columns else 'Datetime'

            fig_residual = px.scatter(df, x='index', y='Magnetic_Field', custom_data=custom_data,
                                      labels={
                                          "index": "Index",
                                          "Magnetic_Field": "Magnetic Field",
                                      }, title="Magnetic Field vs Recording Index"
                                      )
            fig_residual.data[0].update(mode='lines+markers')
            fig_residual.update_layout(template='plotly_dark')
            fig_residual.update_traces(marker={'size': 2})

            return fig_residual, session_store_patch, True
    elif triggered == 'show-previous-residual-plot-durn' and previous_button is not None:
        if diurnal_correction is not None and diurnal_correction > 0:

            surf_df_diurnal_computed = perform_diurnal_correction(active_project, session_store)

            session_store_patch[AppConfig.SURVEY_DATA_START_IDX] = start = max(
                session_store[AppConfig.SURVEY_DATA_START_IDX] - 50000, 0) \
                if AppConfig.SURVEY_DATA_START_IDX in session_store else 0

            end = min(start + 50000, len(surf_df_diurnal_computed))

            surf_df_diurnal_computed = surf_df_diurnal_computed.iloc[start:end]

            fig = generate_line_plot(surf_df_diurnal_computed)

            return fig, session_store_patch, False
        else:
            session_store_patch[AppConfig.SURVEY_DATA_START_IDX] = start = max(
                session_store[AppConfig.SURVEY_DATA_START_IDX] - 50000, 0) \
                if AppConfig.SURVEY_DATA_START_IDX in session_store else 0

            end = start + 50000

            dataset_id = session_store[AppConfig.SURVEY_DATA_SELECTED]

            active_project = ProjectService.get_project_by_id(
                project_id=session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT],
                session=session_store)

            df = get_or_download_dataframe(project=active_project, session_store=session_store,
                                           dataset_type='SURVEY_DATA', dataset_id=dataset_id)

            df = df.set_index('Datetime').sort_index().reset_index().reset_index()
            df = df.iloc[start:end]

            custom_data = 'index' if 'index' in df.columns else 'Datetime'

            fig_residual = px.scatter(df, x='index', y='Magnetic_Field', custom_data=custom_data,
                                      labels={
                                          "index": "Index",
                                          "Magnetic_Field": "Magnetic Field",
                                      }, title="Magnetic Field vs Recording Index"
                                      )
            fig_residual.data[0].update(mode='lines+markers')
            fig_residual.update_layout(template='plotly_dark')
            fig_residual.update_traces(marker={'size': 2})

            return fig_residual, session_store_patch, True
    else:
        return no_update, no_update, no_update


def generate_line_plot(surf_df_diurnal_computed):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=surf_df_diurnal_computed.reset_index()['index'],
                             y=surf_df_diurnal_computed['Magnetic_Field'],
                             mode='lines',
                             name='Original Magnetic Field'))
    fig.add_trace(go.Scatter(x=surf_df_diurnal_computed.reset_index()['index'],
                             y=surf_df_diurnal_computed['Magnetic_Field_Corrected'],
                             mode='lines',
                             name='Magnetic Field Corrected'))
    fig.update_layout(
        title=f"Diurnal Correction of Magnetic Field",
        xaxis_title="Index",
        yaxis_title="Magnetic_Field",
    )
    fig.update_layout(template='plotly_dark')
    return fig


@cache.memoize(timeout=50000, args_to_ignore=['session_store'])
def perform_diurnal_correction(active_project, session_store):
    obs_dfs = []
    d_ids = session_store[AppConfig.OBS_DATA_SELECTED]
    for d_id in d_ids:
        obs_dfs.append(get_or_download_dataframe(session_store=session_store, project=active_project,
                                                 dataset_type='OBSERVATORY_DATA', dataset_id=d_id))
    obs_df = concat_dfs(obs_dfs)
    s_id = session_store[AppConfig.SURVEY_DATA_SELECTED]
    surf_df = get_or_download_dataframe(session_store=session_store, project=active_project,
                                        dataset_type='SURVEY_DATA', dataset_id=s_id)
    surf_df_diurnal_computed = ResidualService \
        .calculate_diurnal_correction(df_surf=surf_df, df_obs=obs_df, session_store=session_store)

    return surf_df_diurnal_computed


@callback(
    Output({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
            'prev': 'None', 'action': 'skip'}, 'disabled', allow_duplicate=True),
    Output({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
            'prev': 'None', 'action': 'next'}, 'disabled', allow_duplicate=True),
    Input("select-survey-data", "value"),
    Input("select-observatory-data", "value"),
    State('local', 'data'),
    prevent_initial_call=True
)
def manage_next_skip_state(survey_data, observatory_data, session_store):
    triggered = callback_context.triggered
    if not triggered:
        raise PreventUpdate
    elif not (survey_data or observatory_data):
        raise PreventUpdate
    else:
        skip_state, next_state = False, True

        survey_data_selected = None
        if triggered[0]['prop_id'] == 'select-survey-data.value':
            survey_data_selected = survey_data

        diurnal_computed = os.path.exists(os.path.join(AppConfig.PROJECT_ROOT, "data",
                                                       session_store[AppIDAuthProvider.APPID_USER_NAME],
                                                       "processed",
                                                       f'{survey_data_selected}_durn.csv'))

        if not survey_data:
            return True, True

        if survey_data and not observatory_data:
            if diurnal_computed:
                skip_state, next_state = False, False
        elif survey_data and observatory_data and diurnal_computed:
            skip_state, next_state = False, False
        else:
            skip_state, next_state = False, True

    return skip_state, next_state


@callback(
    Output("tabs", "active_tab", allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
           'prev': 'None', 'action': 'skip'}, "n_clicks"),
    Input({'type': 'btn', 'subset': 'main-proj-flow', 'next': 'mag_data',
           'prev': 'None', 'action': 'next'}, "n_clicks"),
    State('local', 'data'),
    prevent_initial_call=True
)
def set_data_for_mag_stage(skip_button, next_button, session_store):
    triggered = callback_context.triggered

    if type(triggered) is not str and len(triggered) != 1:
        return no_update
    else:
        triggered = callback_context.triggered_id

    if not triggered:
        raise PreventUpdate
    elif triggered['action'] == 'next' and not next_button:
        raise PreventUpdate
    elif triggered['action'] == 'skip' and not skip_button:
        raise PreventUpdate
    else:
        if triggered['action'] == 'next':

            if session_store[AppConfig.DIURNAL_COMPUTED]:
                obs_ids = ';'.join(session_store[AppConfig.OBS_DATA_SELECTED])

                durn_file_path = os.path.join(AppConfig.PROJECT_ROOT, "data",
                                              session_store[AppIDAuthProvider.APPID_USER_NAME],
                                              "processed",
                                              f'{session_store[AppConfig.SURVEY_DATA_SELECTED]}_{obs_ids}_durn.csv')

                project_id = session_store[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT]
                active_project = ProjectService.get_project_by_id(session=session_store,
                                                                  project_id=project_id)
                parent_dataset_id = session_store[AppConfig.SURVEY_DATA_SELECTED]
                existing_dataset = DatasetService.get_dataset_by_id(parent_dataset_id,
                                                                    session_store=session_store)
                is_update = False
                existing_dataset_id = None
                existing_tags = None
                for dat in active_project.datasets:
                    if str(dat.dataset.parent_dataset_id) == str(existing_dataset.id) \
                            and dat.dataset.tags['state'] == 'DIURNALLY_CORRECTED':
                        is_update = True
                        existing_dataset_id = dat.dataset.id
                        existing_tags = dat.dataset.tags

                existing_tags['state'] = 'DIURNALLY_CORRECTED'

                new_dataset_id = str(uuid.uuid4()) if not is_update else existing_dataset_id

                new_file_path = os.path.join(AppConfig.PROJECT_ROOT, "data",
                                             session_store[AppIDAuthProvider.APPID_USER_NAME],
                                             "downloads",
                                             f'{new_dataset_id}.csv'
                                             )

                shutil.move(src=durn_file_path, dst=new_file_path)
                azr_path = '{}.csv'.format(new_dataset_id)

                try:
                    if not is_update:
                        link_state = 'DIURNALLY_CORRECTED'
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
                        created_dataset = DatasetService.create_new_dataset(dataset=new_dataset, session=session_store)
                    else:
                        print(f'Updating existing diurnal correction dataset with id: {new_dataset_id}')

                        updated_dataset = DatasetService.update_dataset(dataset_id=existing_dataset_id,
                                                                        session_store=session_store,
                                                                        dataset_update_dto=DatasetUpdateDTO(
                                                                            tags=existing_tags))

                    uploader_thread = threading.Thread(
                        target=BlobConnector.upload_blob, kwargs={
                            'blob_name': azr_path,
                            'user_id': session_store[AppIDAuthProvider.APPID_USER_BACKEND_ID],
                            'local_file_path': new_file_path,
                            'linked': False
                        })
                    uploader_thread.start()

                    cache.delete_memoized(DatasetService.get_dataset_by_id)
                    cache.delete_memoized(ProjectService.get_project_by_id)

                    session[AppConfig.WORKING_DATASET] = new_dataset_id
                    return "mag_data"
                except:
                    pass
        else:
            session[AppConfig.WORKING_DATASET] = session_store[AppConfig.SURVEY_DATA_SELECTED]
            return "mag_data"
