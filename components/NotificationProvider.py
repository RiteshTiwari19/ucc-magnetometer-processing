from dash import Output, Input, callback

from FlaskCache import background_callback_manager
from utils import Consts


# @callback(
#     Output("notify-container-placeholder-div", "children"),
#     Input("stepper-next-button", "n_clicks"),
#     prevent_initial_call=True,
#     background=True,
#     manager=background_callback_manager
# )
# def notify(n_intervals):
#     return "Hi"
#     # print(session[Consts.Consts.NOTIFS_MESSAGE])
#     # if Consts.Consts.NOTIFS_MESSAGE not in session:
#     #     raise PreventUpdate
#     # else:
#     #     children_content = session[Consts.Consts.NOTIFS_MESSAGE].split(';')
#     #     if children_content[0] == Consts.Consts.LOADING_DISPLAY_STATE:
#     #         return dmc.Notification(
#     #             id="my-notification",
#     #             title=children_content[1],
#     #             message=children_content[2],
#     #             loading=True,
#     #             color="orange",
#     #             action="show",
#     #             autoClose=False,
#     #             disallowClose=True,
#     #         )
#     #     elif children_content[0] == Consts.Consts.FINISHED_DISPLAY_STATE:
#     #         return dmc.Notification(
#     #             id="my-notification",
#     #             title=children_content[1],
#     #             message=children_content[2],
#     #             color="green",
#     #             action="update",
#     #             icon=DashIconify(icon="akar-icons:circle-check"),
#     #         )
