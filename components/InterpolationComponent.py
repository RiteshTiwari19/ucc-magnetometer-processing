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
        html.Div(ResidualComponent.get_page_tags(active_project, tags_to_add={
            'Stage': 'Interpolation'
        }), id='mag-data-tags-div',
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
        html.Div(children=[
            dmc.Group(children=[
                dmc.Button('Previous', variant='outline', color='blue',
                           id={'type': 'btn', 'subset': 'main-proj-flow', 'next': 'None',
                               'prev': 'mag_data', 'action': 'previous'}
                           )
            ])
        ],
            className='fix-bottom-right')
    ],
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'width': '100%'
        })

    return interpoation_page
