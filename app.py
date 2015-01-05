import os
import logging

import requests
import redis

import flask
from flask import Flask, request
app = Flask(__name__)


r = redis.StrictRedis(
    host=os.getenv('REDIS_PORT_6379_TCP_ADDR'),
    port=os.getenv('REDIS_PORT_6379_TCP_PORT')
)

TEMPLATE = os.getenv('FRONTEND_TEMPLATE')
MARATHON_URL = os.getenv('MARATHON_URL', 'http://localhost:8080')


@app.route('/api/v1/info', methods=['GET'])
def index():
    response = {
        'connection': {},
        'frontends': {}
    }
    try:
        r.ping()
        response['connection']['redis'] = 'OK'
    except Exception as e:
        app.logger.exception(e)
        response['connection']['redis'] = 'cant connect: ' + str(e)

    try:
        requests.get(MARATHON_URL + '/metrics').raise_for_status()
        response['connection']['marathon'] = 'OK'
    except Exception as e:
        app.logger.exception(e)
        response['connection']['marathon'] = 'cant connect: ' + str(e)

    if response['connection']['redis'] == 'OK':
        for frontend in r.keys(pattern='frontend*'):
            response['frontends'][frontend] = []
            for backend in r.lrange(frontend, 0, -1):
                response['frontends'][frontend].append(backend)

    return flask.jsonify(response)


@app.route("/status", methods=['GET'])
def status():
    # for now, just hit these and hope for the best ;)
    r.ping()
    requests.get(MARATHON_URL + '/metrics').raise_for_status()
    return 'OK'


def _appid_from_event(event):
    if 'appId' in event:
        return event['appId']

    else:
        return event['currentStep']['actions'][0]['app']


@app.route("/event", methods=['POST'])
def event():
    data = request.json

    if data['eventType'] in ('status_update_event', 'deployment_step_success', ):
        app_id = _appid_from_event(data)

        response = requests.get(MARATHON_URL + '/v2/tasks')

        def _filter(x):
            return x['appId'] == app_id

        items = filter(_filter, response.json()['tasks'])

        domain = TEMPLATE.format(app_id[1:])
        frontend = 'frontend:{}'.format(domain)

        # clear out all previous backends for this frontend
        for _ in range(len(r.lrange(frontend, 0, -1))):
            r.lpop(frontend)

        for item in items:
            # assumes one PORT per app
            backend = 'http://{}:{}'.format(item['host'], item['ports'][0])
            r.lpush(frontend, backend)

        n = len(items)
        app.logger.debug('Updating {} backend(s) for {}'.format(n, frontend))

    return "OK"


if __name__ == "__main__":
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    app.logger.addHandler(logging.StreamHandler())
    app.logger.setLevel(logging.DEBUG)
    app.run(debug=debug, host='0.0.0.0', port=int(os.getenv('PORT', '5000')))
