from celery import Celery
from dash import CeleryManager
from flask import Flask

from FlaskCache import cache

celery_app = Celery(__name__,
                    broker='redis://localhost:6379/0',
                    backend='redis://localhost:6379/1',
                    )

default_config = "CeleryConfig"

celery_app.config_from_object(default_config)

background_callback_manager = CeleryManager(celery_app)

flask = Flask(__name__)
cache.init_app(flask, config={
    'CACHE_TYPE': 'simple'
})
