import time

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from datetime import datetime, date
import numpy as np
import plotly.express as px
from dash import dcc, html, Input, Output, State, Patch, no_update, ALL, callback, clientside_callback, callback_context
from dash_iconify import DashIconify
from flask import session

from api import ResidualService
from api.ProjectsService import ProjectService
from auth import AppIDAuthProvider
from components import ModalComponent, MapboxScatterPlot, MagDataComponent
from dataservices import InMermoryDataService


#
#
# def get_mag_data_page(session):
#     active_project = InMermoryDataService.WorkspaceService.get_project_by_name(session['current_active_project'])
#     active_session = session[AppIDAuthProvider.APPID_USER_NAME]
#
#     tag_buttons = [dmc.Group([dmc.Button(
#         [
#             f"{key.upper()}: ",
#             dmc.Badge(f"{value}", color="secondary", className="ms-1", variant='gradient',
#                       gradient={"from": "indigo", "to": "cyan"}),
#         ],
#         style={'display': 'inline-block', 'margin': '10px', 'padding': '5px'}, variant='subtle', color='gray'
#     )
#     ]) for key, value in active_project.items()]

    # mag_data_page = html.Div([
    #     html.Div(ModalComponent.get_upload_data_modal(configured_du,
    #                                                   upload_id=session[AppIDAuthProvider.APPID_USER_NAME]),
    #              style={'width': '100%'}),
    #     html.Div(tag_buttons, id='mag-data-tags-div',
    #              style={
    #                  'display': 'flex',
    #                  'flexDirection': 'row',
    #                  'flexWrap': 'wrap',
    #                  'alignItems': 'space-between',
    #                  'justifyContent': 'flex-start'
    #              }),
    #     html.Br(),
        # html.Div([
        #     html.Span('Please', style={'marginRight': '1.5rem'}),
        #     dmc.Select(
        #         data=drop_down_options,
        #         id='dropdown-dataset',
        #         searchable=True,
        #         nothingFound="No dataset found",
        #         icon=DashIconify(icon="bxs:data"),
        #         persistence=False,
        #         placeholder='Select Dataset',
        #         selectOnBlur=True,
        #         clearable=True,
        #         required=True
        #     ),
        #
        #     html.Span('an existing dataset', style={'marginLeft': '1.5rem'}),
        #     html.Div(dbc.Badge('OR', color="secondary", text_color="white",
        #                        className="ms-1"), style={'marginLeft': '1.5rem'}),
        #
        #     dbc.Button("Upload", color="primary", style={'marginLeft': '1.5rem'},
        #                id={'type': 'button', 'subset': 'modal', 'action': 'open', 'idx': 'open-upload-modal'}),
        #     html.Span('a new one', style={'marginLeft': '1.5rem'})
        # ],
        #     style={
        #         'display': 'flex',
        #         'flexDirection': 'row',
        #         'flexWrap': 'wrap',
        #         'alignItems': 'center',
        #         'justifyContent': 'center'
        #     }, id='select-dataset-div'
        # ),
        # html.Br(),
        # html.Br(),

    #     dmc.Group([
    #         dmc.Stack(
    #             children=[
    #                 dmc.Badge("Ambient Smoothing Constant", color="wine-red", className="ms-1", variant='color',
    #                           style={'maxWidth': '50%'}),
    #                 dmc.Slider(
    #                     id="ambient-smoothing-slider",
    #                     value=500,
    #                     updatemode="drag",
    #                     min=0,
    #                     max=1000,
    #                     color='wine-red',
    #                     size='lg',
    #                     radius=10,
    #                     labelTransitionTimingFunction='ease',
    #                     labelTransition='scale-x',
    #                     labelTransitionDuration=600,
    #                     marks=[{'label': i, "value": i} for i in np.arange(100, 1000, 100)],
    #                     style={'width': '100%'}
    #                 )],
    #             style={'width': '40%'}),
    #
    #         dmc.Stack([
    #             dmc.Badge("Observed Smoothing Constant", color="cyan", className="ms-1", variant='color',
    #                       style={'maxWidth': '50%'}),
    #             dmc.Slider(
    #                 id="observed-smoothing-slider",
    #                 value=100,
    #                 updatemode="drag",
    #                 min=0,
    #                 max=200,
    #                 color='cyan',
    #                 labelTransitionTimingFunction='ease',
    #                 labelTransition='scale-x',
    #                 labelTransitionDuration=600,
    #                 size='lg',
    #                 radius=10,
    #                 marks=[{'label': i, "value": i} for i in np.arange(10, 200, 20)],
    #                 style={'width': '100%'}
    #             )], style={'width': '40%'}),
    #
    #         dmc.Button("Apply", variant='outline', color='secondary', id='calc-residuals-btn')
    #
    #     ], spacing='lg', className='show-div', id='smoothing-constant-div', position='center'),
    #
    #     html.Br(),
    #     html.Br(),
    #
    #
    #
    # ],
    #     style={
    #         'display': 'flex',
    #         'flexDirection': 'column',
    #         'width': '100%'
    #     },
    #     # className="bg-dark rounded-3"
    # )
    #
    # return mag_data_page
#
def get_interpolation_page(session):
    active_project = ProjectService.get_project_by_id(session=session,
                                                      project_id=session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])
    interpoation_page = html.Div([
        html.Div(MagDataComponent.get_page_tags(active_project), id='mag-data-tags-div',
                 style={
                     'display': 'flex',
                     'flexDirection': 'row',
                     'flexWrap': 'wrap',
                     'alignItems': 'space-between',
                     'justifyContent': 'flex-start'
                 }),
        html.Br(),
        dmc.DatePicker(
            id="date-picker",
            label="Start Date",
            description="You can also provide a description",
            minDate=date(2020, 8, 5),
            value=datetime.now().date(),
            style={"maxWidth": '40%', "width": '40%'},
        ),
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
        ]),

        html.Div(
            children=[
                dmc.LoadingOverlay(children=
                [
                    html.Div(id='datasets-residuals-plot-interp', style={'flex': 'auto'},
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
                        className='show-div',
                        position='right',
                        id='residual-plot-nex-prev-btn-group'
                    ),

                    html.Br(),
                ],
                    loaderProps={"variant": "dots", "color": "orange", "size": "xl"},
                    className='plot-layout-full-stretch',
                    id={'type': 'plotly', 'location': 'residual', 'idx': 'residuals-plot-interp'}
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
                    id={'type': 'plotly', 'location': 'residual', 'idx': 'open-map-plot-interp'}
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
    ],
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'width': '100%'
        })

    return interpoation_page
