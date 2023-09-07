import time
from typing import List

import dash
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from dash import no_update, callback, clientside_callback, ALL, MATCH
from dash_iconify import DashIconify

from api.DatasetService import DatasetService
from api.dto import DatasetFilterDTO, DatasetsWithDatasetTypeDTO


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
    dataset_papers = []

    for dataset in datasets:
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
                            ], className='stack-small-gap')
                        ],
                        position='apart'
                    )
                ],
                radius='md',
                shadow='lg',
                p='md')
        dataset_papers.append(dataset_paper)
    return dmc.Stack(children=dataset_papers, align='stretch', mt='lg')
