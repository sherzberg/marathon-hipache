import os
import logging

import requests
import redis

from flask import Flask, request
app = Flask(__name__)


r = redis.StrictRedis(
    host=os.getenv('REDIS_PORT_6379_TCP_ADDR'),
    port=os.getenv('REDIS_PORT_6379_TCP_PORT')
)

TEMPLATE = os.getenv('FRONTEND_TEMPLATE')


@app.route("/status", methods=['GET'])
def status():
    return 'OK'


@app.route("/event", methods=['POST'])
def event():
    data = request.json

    if data['eventType'] == 'deployment_step_success':
        app_id = data['currentStep']['actions'][0]['app']

        response = requests.get('http://localhost:8080/v2/tasks')

        items = filter(lambda x: x['appId'] == app_id, response.json()['tasks'])

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
