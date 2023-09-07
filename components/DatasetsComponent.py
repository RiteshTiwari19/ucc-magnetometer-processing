from typing import List

import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_mantine_components as dmc
from dash import State, html, Input, Output, Patch, ALL, callback, clientside_callback, MATCH, callback_context, \
    no_update
from dash.exceptions import PreventUpdate
from dash_iconify import DashIconify

from FlaskCache import cache
from api import ProjectsService
from api.DatasetService import DatasetService
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
    datasets: List[DatasetsWithDatasetTypeDTO] = DatasetService.get_datasets(session=session_store,
                                                                             datasets_filter=datasets_filter)
    dataset_papers = [html.Div(id='choose-project-link-modal')]

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
                                            dmc.MenuItem("CSV",
                                                         icon=DashIconify(icon="iwwa:csv", color="lime"),
                                                         style={
                                                             'width': '100%'
                                                         }
                                                         ),
                                            dmc.MenuItem("Raster",
                                                         icon=DashIconify(icon="vaadin:raster", color="lime"),
                                                         style={
                                                             'width': '100%'
                                                         }
                                                         ),
                                            dmc.MenuItem("Shapefile",
                                                         icon=DashIconify(icon="gis:shape-file", color="lime"),
                                                         style={
                                                             'width': '100%'
                                                         }
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
                        position='apart'
                    )
                ],
                radius='md',
                shadow='lg',
                p='md')
        dataset_papers.append(dataset_paper)
    return dmc.Stack(children=dataset_papers, align='stretch', mt='lg')


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
    State({'idx': ALL, 'type': 'backend-search-dropdown'}, "value"),
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
        status = ProjectsService.ProjectService\
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
    if not button_id:
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
                        dcc.Dropdown(id={'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown'})
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
    Output({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown'}, "options"),
    Input({'idx': "link-ds-search-project-dropdown", 'type': 'backend-search-dropdown'}, "search_value"),
    State("local", "data")
)
def update_options(search_value, session_store):
    if not search_value or len(search_value) <= 2:
        raise PreventUpdate

    params = {'project_name': search_value}

    options = ProjectsService.ProjectService.fetch_projects(session_store=session_store, params=params)
    options = [{'label': o.name, 'value': o.id} for o in options]
    return [o for o in options if search_value in o["label"]]
