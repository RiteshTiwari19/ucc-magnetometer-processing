import dash_mantine_components as dmc
from dash import Output, Input, html, callback_context as ctx, no_update, callback, State
from dash_iconify import DashIconify
from dash.exceptions import PreventUpdate
from utils import Consts
from flask import session
from FlaskCache import background_callback_manager


@callback(
    Output("notify-container-placeholder-div", "children"),
    Input("notification-checker", "n_intervals"),
    prevent_initial_call=True,
    background=True,
    manager=background_callback_manager
)
def notify(n_intervals):
    print('HIIIIIIIIIIIIIIII SOMEBODYYYYYYYYYYYYYY')
    return "Hi"
    # print(session[Consts.Consts.NOTIFS_MESSAGE])
    # if Consts.Consts.NOTIFS_MESSAGE not in session:
    #     raise PreventUpdate
    # else:
    #     children_content = session[Consts.Consts.NOTIFS_MESSAGE].split(';')
    #     if children_content[0] == Consts.Consts.LOADING_DISPLAY_STATE:
    #         return dmc.Notification(
    #             id="my-notification",
    #             title=children_content[1],
    #             message=children_content[2],
    #             loading=True,
    #             color="orange",
    #             action="show",
    #             autoClose=False,
    #             disallowClose=True,
    #         )
    #     elif children_content[0] == Consts.Consts.FINISHED_DISPLAY_STATE:
    #         return dmc.Notification(
    #             id="my-notification",
    #             title=children_content[1],
    #             message=children_content[2],
    #             color="green",
    #             action="update",
    #             icon=DashIconify(icon="akar-icons:circle-check"),
    #         )
