import base64
import functools
import json
import logging
import dash_bootstrap_components as dbc
import jwt
import pkce
import requests
from dash import html, dcc, no_update
from FlaskCache import cache
from flask import Flask, redirect, request, session
from jwt.exceptions import ExpiredSignatureError

from api import UserService
from dataservices.RedisQueue import RedisQueue


class AppIDAuthProvider:
    # App ID

    # CLIENT_ID = os.environ["APPID_CLIENT_ID"]
    # TENANT_ID = os.environ["TENANT_ID"]
    # CLIENT_SECRET = os.environ["APPID_CLIENT_SECRET"]
    # REDIRECT_URI = os.environ["APPID_REDIRECT_URI"]
    # OAUTH_SERVER_URL = os.environ["APPID_OAUTH_SERVER_URL"]
    # JWKS_URL = os.environ["JWKS_URL"]


    # Session

    APPID_USER_TOKEN = "APPID_USER_TOKEN"
    APPID_ID_TOKEN = "APPID_ID_TOKEN"
    APPID_USER_ROLES = "APPID_USER_ROLES"
    APPID_USER_EMAIL = "APPID_USER_EMAIL"
    APPID_USER_BACKEND_ID = "APPID_USER_BACKEND_ID"
    AUTH_ERRMSG = "AUTH_ERRMSG"
    ENDPOINT_CONTEXT = "ENDPOINT_CONTEXT"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    APPID_USER_NAME = "APPID_USER_NAME"
    CURRENT_ACTIVE_PROJECT = "current_active_project"
    LAST_DATASET_UPLOADED = "last_dataset_uploaded"
    DATASET_TYPE_SELECTED = "dataset_type_selected"
    PLOTLY_SCATTER_PLOT_SUBSET = "plotly_scatter_plot_subset"
    DATASET_NAME = "dataset_name"

    def __init__(self, dash_url):
        logging.basicConfig(level=logging.INFO)

        self.flask = Flask(__name__)
        cache.init_app(self.flask, config={
            'CACHE_TYPE': 'simple'
        })

        self.redis_queue = RedisQueue(name='app-notifications')

        # self.flask.secret_key = os.environ["SESSION_SECRET_KEY"]
        self.flask.secret_key = "test.py-secret-key"

        @self.flask.route("/")
        def index():
            auth_active, _ = AppIDAuthProvider._is_auth_active()
            if auth_active:
                return redirect(dash_url)
            else:
                return redirect("/startauth")

        @self.flask.route("/startauth")
        def start_auth_route():
            session[AppIDAuthProvider.ENDPOINT_CONTEXT] = request.path if request.path != '/startauth' else dash_url
            # print(session[AppIDAuthProvider.ENDPOINT_CONTEXT])
            return AppIDAuthProvider.start_auth()

        @self.flask.route("/afterauth", methods=["POST"])
        def after_auth():

            # This route is pre-registered with the App ID service instance as
            # the 'redirect' URI, so that it can redirect the flow back into
            # the application after successful authentication
            err_msg = ""
            if "code" in request.form:
                code = request.form['code']
                id_token = request.form['id_token']
                # Send the authorization code to the token endpoint to retrieve access_token and id_token
                token_endpoint = AppIDAuthProvider.OAUTH_SERVER_URL + "/token"
                cvf = session['cvf']
                resp = requests.post(token_endpoint,
                                     headers={'Origin': 'http://localhost'},
                                     data={"client_id": AppIDAuthProvider.CLIENT_ID,
                                           "grant_type": "authorization_code",
                                           "redirect_uri": AppIDAuthProvider.REDIRECT_URI,
                                           "code": code,
                                           "scope": "api://ucc-mag-app-api/Middleware",
                                           "code_verifier": cvf})
                resp_json = resp.json()
                if "error_description" in resp_json:
                    err_msg = "Could not retrieve user tokens, {}".format(resp_json["error_description"])
                elif "id_token" in resp_json and "access_token" in resp_json:
                    access_token = resp_json["access_token"]
                    id_token = resp_json["id_token"]
                    # print(f'id_token: {id_token}')
                    user_email, user_id, roles, user_name = AppIDAuthProvider._get_user_info(resp_json["id_token"])

                    internal_user_id = UserService.UserService.get_user_by_id(
                        session={
                            'APPID_USER_TOKEN': access_token,
                            'APPID_USER_EMAIL': user_email
                        })

                    session[AppIDAuthProvider.APPID_USER_BACKEND_ID] = internal_user_id.id

                    if roles is not None:
                        print(access_token)
                        session[AppIDAuthProvider.APPID_USER_TOKEN] = access_token
                        session[AppIDAuthProvider.APPID_ID_TOKEN] = id_token
                        session[AppIDAuthProvider.APPID_USER_ROLES] = roles
                        session[AppIDAuthProvider.APPID_USER_EMAIL] = user_email
                        session[AppIDAuthProvider.APPID_USER_NAME] = user_name
                        logging.info(" User {} logged in".format(user_email))
                    else:
                        err_msg = "Could not retrieve user roles"
                        if "error_description" in resp_json:
                            err_msg = err_msg + ", " + resp_json["error_description"]
                else:
                    err_msg = "Did not receive 'id_token' and / or 'access_token'"
            else:
                err_msg = "Did not receive 'code' from the authorization server"
            if err_msg:
                logging.error(err_msg)
                session[AppIDAuthProvider.AUTH_ERRMSG] = err_msg
                # session.modified = True
            endpoint_context = session.pop(AppIDAuthProvider.ENDPOINT_CONTEXT, None)
            return redirect(endpoint_context)

    @classmethod
    def get_cache(cls):
        return cls.cache

    @classmethod
    def check(cls, func):
        @functools.wraps(func)
        def wrapper_check(*args, **kwargs):
            session[AppIDAuthProvider.LAST_DATASET_UPLOADED] = 'NONE'
            auth_active, err_msg = cls._is_auth_active()
            if not auth_active:
                if err_msg:
                    if err_msg == AppIDAuthProvider.SESSION_EXPIRED:
                        return [
                            html.Div(
                                dbc.Row(
                                    dbc.Col(dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.H5("User Session Expired", className="card-title"),
                                                html.P("Please log in again to continue using the application"),
                                                html.Div(children=[
                                                    html.A("Log in", href="/startauth", role='button',
                                                           className='btn btn-primary col-6')
                                                ], style={'display': 'flex',
                                                          'flexDirection': 'row',
                                                          'justifyContent': 'center'
                                                          }),

                                            ],
                                            style={'textAlign': 'center'}
                                        )
                                    ), style={'size': '100%'})
                                ), style={'width': '100%'})

                        ], no_update

                    err_msg = "Internal error: " + err_msg
                    return [html.Div(children=err_msg,
                                     style={"textAlign": "center", "font-size": "20px", "color": "red"})], no_update
                else:
                    return [
                        html.Div(
                            dbc.Row(
                                dbc.Col(dbc.Card(
                                    dbc.CardBody(
                                        [
                                            html.H5("User not logged in", className="card-title"),
                                            html.P("Please log in to use the application"),
                                            html.Div(children=[
                                                html.A("Log in", href="/startauth", role='button',
                                                       className='btn btn-primary col-6')
                                            ], style={'display': 'flex',
                                                      'flexDirection': 'row',
                                                      'justifyContent': 'center'
                                                      }),

                                        ],
                                        style={'textAlign': 'center'}
                                    )
                                ), style={'size': '100%'})
                            ), id='no-auth', style={'width': '100%'})

                    ], no_update
            else:
                if not cls._user_has_a_role():
                    return [html.Div(children="Unauthorized!",
                                     style={"textAlign": "center", "font-size": "20px", "color": "red"})], no_update
                else:
                    return func(*args, **kwargs)

        return wrapper_check

    @classmethod
    def validate_token_with_jwks(cls, token):
        jwks_response = requests.get(AppIDAuthProvider.JWKS_URL)
        jwks_response.raise_for_status()
        jwks = json.loads(jwks_response.content)

        public_keys = {}
        for jwk in jwks['keys']:
            kid = jwk['kid']
            public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

        kid = jwt.get_unverified_header(token)['kid']
        key = public_keys[kid]

        payload = jwt.decode(token, key=key, algorithms=['RS256'], audience=AppIDAuthProvider.CLIENT_ID)
        print(session[AppIDAuthProvider.APPID_USER_TOKEN])
        print(payload)
        return payload

    @classmethod
    def _is_auth_active(cls):
        if cls.AUTH_ERRMSG in session:
            return False, session.pop(cls.AUTH_ERRMSG)
        elif cls.APPID_ID_TOKEN in session:
            token = session[cls.APPID_ID_TOKEN]
            try:
                introspect_endpoint = cls.validate_token_with_jwks(token)
            except Exception as ex:
                if type(ex) == ExpiredSignatureError:
                    return False, ("%s" % AppIDAuthProvider.SESSION_EXPIRED)
                else:
                    err_msg = str(ex)
                    err_msg = "Could not introspect user token, {}".format(err_msg)
                    logging.error(err_msg)
                    session.pop(cls.APPID_ID_TOKEN, None)
                    session.pop(cls.APPID_USER_TOKEN, None)
                    session.pop(cls.APPID_USER_ROLES, None)
                    return False, err_msg
            if introspect_endpoint is not None:
                return True, ""
            else:
                return False, ""
        else:
            return False, ""

    @classmethod
    def start_auth(cls):
        code_verifier, code_challenge = pkce.generate_pkce_pair()
        nonce = 12345
        session['cvf'] = code_verifier

        if cls.ENDPOINT_CONTEXT not in session:
            session[cls.ENDPOINT_CONTEXT] = request.path
            # session.modified = True
        authorization_endpoint = cls.OAUTH_SERVER_URL + "/authorize"

        auth_url = f"{authorization_endpoint}?client_id={cls.CLIENT_ID}&response_type=code%20id_token&redirect_uri={cls.REDIRECT_URI}&nonce={nonce}" + \
                   "&scope=email%20openid%20profile%20offline_access%20https%3A%2F%2Fgraph.microsoft.com%2FMail.Read%20https%3A%2F%2Fgraph.microsoft.com%2FUser.Read%20api%3A%2F%2Fucc-mag-app-api%2FMiddleware" + \
                   "&response_mode=form_post" + \
                   f"&code_challenge={code_challenge}&code_challenge_method=S256"

        return redirect(auth_url)

    @staticmethod
    def _get_user_info(id_token):
        decoded_id_token = AppIDAuthProvider._base64_decode(id_token.split('.')[1])
        id_token_details = json.loads(decoded_id_token)
        roles = id_token_details['roles'] if 'roles' in id_token_details else None
        user_name = id_token_details['name']
        return id_token_details["email"], id_token_details["sub"], roles, user_name

    @staticmethod
    def _base64_decode(data):
        data += '=' * (4 - len(data) % 4)  # pad the data as needed
        return base64.b64decode(data).decode('utf-8')

    @classmethod
    def _user_has_a_role(cls):
        if cls.APPID_USER_ROLES in session and session[cls.APPID_USER_ROLES]:
            return True
        else:
            session.pop(cls.APPID_USER_TOKEN, None)
            session.pop(cls.APPID_USER_ROLES, None)
            return False
