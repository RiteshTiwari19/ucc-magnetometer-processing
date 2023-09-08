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
from components import ModalComponent, MapboxScatterPlot, ResidualComponent
from dataservices import InMermoryDataService


def get_interpolation_page(session):
    active_project = ProjectService.get_project_by_id(session=session,
                                                      project_id=session[AppIDAuthProvider.CURRENT_ACTIVE_PROJECT])
    interpoation_page = html.Div([
        html.Div(ResidualComponent.get_page_tags(active_project), id='mag-data-tags-div',
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
