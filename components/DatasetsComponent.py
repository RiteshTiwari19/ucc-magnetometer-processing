from typing import List
from urllib.parse import quote as urlquote

import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import State, html, Input, Output, ALL, callback, clientside_callback, MATCH, callback_context, \
    no_update
from dash import dcc
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from FlaskCache import cache
from api import ProjectsService
from api.DatasetService import DatasetService
from api.DatasetTypeService import DatasetTypeService
from api.dto import DatasetFilterDTO, DatasetsWithDatasetTypeDTO
from components import Toast


def get_color_based_on_dataset_type(dataset_type_name):
    if dataset_type_name == 'OBSERVATORY_DATA':
        return 'dark-yellow'
    elif dataset_type_name == 'SURVEY_DATA':
        return 'dark-green'
    else:
        return 'dark-yellow'


def get_datasets(session_store, datasets_filter: DatasetFilterDTO | None = None):

    dataset_papers = [html.Div(id='choose-project-link-modal'),
                      dmc.Group([
                          dmc.Group([
                              html.Div([
                                  "Project",
                                  dcc.Dropdown(
                                      id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                                          'sub': 'project-filter'})
                              ], style={'width': '100%'}),
                              html.Div([
                                  "Dataset Type",
                                  dcc.Dropdown(
                                      id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                                          'sub': 'dataset-type-filter'})
                              ], style={'width': '100%'}),

                              dmc.TextInput(label="Dataset Name:", placeholder="Provide a dataset name to filter",
                                            id='dataset-name-filter', icon=DashIconify(icon='ic:sharp-search',
                                                                                       width=30)),
                          ], grow=True, style={'minWidth': '80%'}),
                          dmc.Group([
                              dmc.Button('Filter',
                                         leftIcon=DashIconify(icon="system-uicons:filter", color='dark-green',
                                                              width=20),
                                         variant='filled',
                                         color='blue',
                                         id='filter-datasets-button'
                                         )
                          ], grow=False, maw='200px')

                      ], align='end', grow=True, position='apart')
                      ]

    datasets = get_datasets_from_db(datasets_filter, session_store)

    out = dmc.Stack([
        dmc.Stack(dataset_papers, align='stretch', id='datasets_filter_stack'),
        dmc.Stack(children=datasets, align='stretch', mt='sm', id='datasets_stack')
    ], align='stretch', mt='lg')

    return out


def get_datasets_from_db(datasets_filter, session_store):
    dataset_papers = []
    datasets: List[DatasetsWithDatasetTypeDTO] = DatasetService.get_datasets(session=session_store,
                                                                             datasets_filter=datasets_filter)
    for idx, dataset in enumerate(datasets):
        dataset_paper = \
            dmc.Paper(
                children=[
                    dmc.Group(
                        children=[
                            dmc.Stack(children=[
                                dmc.Group(children=[
                                    dmc.Title(dataset.dataset_type.name.replace('_', ' ').title(),
                                              color=get_color_based_on_dataset_type(dataset.dataset_type.name),
                                              underline=False, order=4),
                                    dmc.ActionIcon(
                                        DashIconify(icon="ooui:next-ltr", width=20, color='dark-gray'),
                                        size="xs"
                                    ),
                                    dmc.Text(dataset.name.upper(), color='blue', weight=700, underline=False),
                                ], style={'column-gap': '1px'}),
                                dmc.Group(children=[
                                    dmc.ActionIcon(
                                        DashIconify(icon="uil:calender", width=20, color='dark-gray'),
                                        size="xs"
                                    ),
                                    dmc.Text('CREATED AT', size='xs'),
                                    dmc.Text(dataset.created_at.strftime("%m/%d/%Y, %H:%M:%S"), color="dimmed",
                                             size='xs')
                                ]),
                                dmc.Group(children=[
                                    dmc.ActionIcon(
                                        DashIconify(icon="uil:calender", width=20, color='dark-gray'),
                                        size="xs"
                                    ),
                                    dmc.Text('MODIFIED AT', size='xs'),
                                    dmc.Text(dataset.modified_at.strftime("%m/%d/%Y, %H:%M:%S"), color="dimmed",
                                             size='xs')
                                ])
                            ]),

                            dmc.Stack(children=[
                                dmc.Button('Delete',
                                           leftIcon=dmc.ActionIcon(
                                               DashIconify(icon="mdi:bin", width=20),
                                               size="lg",
                                               color='wine-red'
                                           ),
                                           variant='outline',
                                           color='wine-red',
                                           id={'type': 'btn', 'subset': 'datasets', 'action': 'delete',
                                               'index': dataset.id}),
                                dmc.Button('Link To Project',
                                           leftIcon=DashIconify(icon="mingcute:link-fill", color='dark-green'),
                                           variant='outline',
                                           color='lime',
                                           id={'type': 'btn', 'subset': 'datasets-modal',
                                               'action': 'link_to_project_modal',
                                               'index': dataset.id, 'dname': dataset.name}),

                                dmc.Menu(
                                    [
                                        dmc.MenuTarget(dmc.Button('Export',
                                                                  leftIcon=dmc.ActionIcon(
                                                                      DashIconify(icon="typcn:export", width=20),
                                                                      size="lg",
                                                                      color='lime'
                                                                  ), style={'width': '100%'}, variant='outline')),
                                        dmc.MenuDropdown(children=
                                        [
                                            dmc.MenuLabel("Format"),
                                            dmc.MenuItem(
                                                "CSV",
                                                href=file_download_link(dataset=dataset,
                                                                        session_store=session_store, dtype='csv'),
                                                target="_blank",
                                                icon=DashIconify(icon="iwwa:csv", color="lime"),
                                            ),
                                            dmc.MenuItem("Raster",
                                                         icon=DashIconify(icon="vaadin:raster", color="lime"),
                                                         href=file_download_link(dataset=dataset,
                                                                                 session_store=session_store,
                                                                                 dtype='raster'),
                                                         target="_blank"
                                                         ),
                                            dmc.MenuItem("Shapefile",
                                                         icon=DashIconify(icon="gis:shape-file", color="lime"),
                                                         href=file_download_link(dataset=dataset,
                                                                                 session_store=session_store,
                                                                                 dtype='zip'),
                                                         target="_blank"
                                                         )
                                        ],
                                            style={'width': '100%'}
                                        ),
                                    ],
                                    trigger="hover",
                                    style={'width': '100%'},
                                    withArrow=True,
                                    position='left'
                                )
                            ], id=f'dataset-btn-stack-{idx}')
                        ],
                        position='apart', id='datasets-view-group'
                    )
                ],
                radius='md',
                shadow='lg',
                p='md')
        dataset_papers.append(dataset_paper)
    return dataset_papers


clientside_callback(
    """
    function(n_clicks) {
        return true
    }
    """,
    Output({'type': 'btn', 'subset': 'datasets', 'action': MATCH, 'index': MATCH}, "loading",
           allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'datasets', 'action': MATCH, 'index': MATCH}, "n_clicks"),
    prevent_initial_call=True,
)

clientside_callback(
    """
    function(nc1, opened) {
        return opened ? false: true
    }
    """,
    Output("modal-link-dataset-to-project", "opened"),
    Input("modal-close-button", "n_clicks"),
    State("modal-link-dataset-to-project", "opened"),
    prevent_initial_call=True,
)


@callback(
    Output('dataset_tabs', 'active_tab'),
    Output("toast-placeholder-div", "children", allow_duplicate=True),
    Input({'type': 'btn', 'subset': 'datasets', 'action': ALL, 'index': ALL}, "n_clicks"),
    State({'idx': ALL, 'type': 'backend-search-dropdown', 'sub': 'link-filter'}, "value"),
    State('local', "data"),
    prevent_initial_call=True
)
def cta_handler(n_clicks, project_id, session_store):
    ct = callback_context
    button_id = ct.triggered_id

    if not any(click for click in n_clicks):
        raise PreventUpdate

    action = button_id['action']
    dataset_id = button_id['index']

    if action == 'delete':
        DatasetService.delete_dataset(dataset_id=dataset_id, session=session_store)
        cache.delete_memoized(DatasetService.get_datasets)
        return "existing_datasets", Toast.get_toast("Notification", 'Dataset deleted successfully', icon='info')
    if action == 'link_to_project':
        status = ProjectsService.ProjectService \
            .link_dataset_to_project(project_id=project_id[0], dataset_id=dataset_id, session_store=session_store)

        if status == 'NO_UPDATE':
            toast = Toast.get_toast("Notification", 'Dataset Already Linked to Project', icon='info')
        else:
            toast = Toast.get_toast("Notification", 'Dataset Linked to Project', icon='info')

        return "existing_datasets", toast
    return "existing_datasets", no_update


@callback(
    Output('choose-project-link-modal', 'children'),
    Input({'type': 'btn', 'subset': 'datasets-modal', 'action': 'link_to_project_modal',
           'index': ALL, 'dname': ALL}, "n_clicks"),
    State('local', "data"),
    prevent_initial_call=True
)
def open_modal(n_clicks, session_store):
    ct = callback_context
    button_id = ct.triggered_id
    if not any(click for click in n_clicks):
        raise PreventUpdate

    dataset_id = button_id['index']
    dataset_name = button_id['dname']

    return get_link_to_project_modal(dataset_id, dataset_name)


def get_link_to_project_modal(dataset_id, dataset_name):
    return html.Div(
        [
            dmc.Modal(
                title="Link Dataset to Project",
                id="modal-link-dataset-to-project",
                zIndex=10000,
                opened=True,
                centered=True,
                children=[
                    dmc.Group([
                        dmc.Text("Dataset", weight=500, underline=False),
                        dmc.Text(dataset_name, id='dataset_link_id', color='dimmed')
                    ]),

                    dmc.Space(h=15),

                    html.Div([
                        "Search Project",
                        dcc.Dropdown(id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown',
                                         'sub': 'link-filter'})
                    ]),

                    dmc.Space(h=20),
                    dmc.Group(
                        [
                            dmc.Button("Submit",
                                       id={'type': 'btn', 'subset': 'datasets', 'action': 'link_to_project',
                                           'index': dataset_id}),
                            dmc.Button(
                                "Close",
                                color="red",
                                variant="outline",
                                id="modal-close-button",
                            ),
                        ],
                        position="right",
                    ),
                ],
            ),
        ]
    )


@callback(
    Output({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': MATCH}, "options"),
    Input({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': MATCH}, "search_value"),
    State("local", "data")
)
def update_options(search_value, session_store):
    if not search_value or len(search_value) <= 2:
        raise PreventUpdate

    triggered = callback_context.triggered_id
    subject = triggered['sub']

    if subject == 'link-filter' or subject == 'project-filter':
        params = {'project_name': search_value}

        options = ProjectsService.ProjectService.fetch_projects(session_store=session_store, params=params)
        options = [{'label': o.name, 'value': o.id} for o in options]

        return options

    elif subject == 'dataset-type-filter':
        data_types = DatasetTypeService.get_dataset_types(session=session_store)
        options = [{'label': data_type.name, 'value': data_type.id} for data_type in data_types]
        return options
    else:
        return no_update


@callback(
    Output('datasets_stack', 'children'),
    Input('filter-datasets-button', 'n_clicks'),
    State('dataset-name-filter', 'value'),
    State({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': 'project-filter'}, 'value'),
    State({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown', 'sub': 'dataset-type-filter'}, 'value'),
    State('local', 'data'),
    prevent_initial_update=True
)
def filter_datasets(n_clicks, dataset_name_query, project_query, dataset_type_query, session_store):
    if not n_clicks:
        raise PreventUpdate
    else:
        dataset_filter_dto: DatasetFilterDTO = DatasetFilterDTO()
        if dataset_name_query:
            dataset_filter_dto.dataset_name = dataset_name_query

        if dataset_type_query:
            dataset_filter_dto.dataset_type_id = dataset_type_query

        if project_query:
            dataset_filter_dto.project_id = project_query

    return get_datasets_from_db(datasets_filter=dataset_filter_dto, session_store=session_store)


def file_download_link(dataset, session_store, dtype='csv'):
    location = "/download/{}.{}____{}/{}".format(urlquote(dataset.name), dtype, dataset.path, dataset.id)
    return location
