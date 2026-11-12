#!/usr/bin/env python

import argparse
import sys
import omero.clients
import Ice

from prometheus_client import (
    Gauge,
    start_http_server,
)
from time import sleep
from omero_prometheus_tools import (
    CountMetrics,
    SessionMetrics,
)


def connect(hostname, username, password):
    client = omero.client(hostname)
    client.setAgent('prometheus-omero-tools')
    client.createSession(username, password)
    # Ping the server periodically so the session and connection are not
    # dropped as idle when the update interval is long (e.g. 3600s)
    client.enableKeepAlive(KEEPALIVE_SECONDS)
    return client


def close_quietly(client):
    try:
        client.closeSession()
    except Exception:
        pass


KEEPALIVE_SECONDS = 60


def positive_int(value):
    int_value = int(value)
    if int_value <= 0:
        raise argparse.ArgumentTypeError(f'{value} is not a positive int')
    return int_value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='append',
                        help='Query configuration files')
    parser.add_argument('-d', '--disable-session', action='store_true',
                        help='Disable session metrics')
    parser.add_argument('-s', '--host', default='localhost')
    parser.add_argument('-u', '--user', default='guest')
    parser.add_argument('-w', '--password', default='guest')
    parser.add_argument('-l', '--listen', type=int, default=9449,
                        help='Serve metrics on this port')
    parser.add_argument('-i', '--interval', type=positive_int, default=60,
                        help='Interval (seconds) between updates, default 60')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print verbose output')
    args = parser.parse_args()

    if not args.config and args.disable_session:
        parser.error('Either config or session metrics must be enabled')

    g_last_login = Gauge('omero_prometheus_tools_agent_login_time',
                         'Time of last Prometheus agent login')

    client = connect(args.host, args.user, args.password)
    # Don't catch exception, exit on login failure so user knows
    g_last_login.set_to_current_time()

    try:
        # Start up the server to expose the metrics.
        start_http_server(args.listen)
        if args.config:
            counts = CountMetrics(client, args.config, args.verbose)
        else:
            counts = None
        if args.disable_session:
            sessions = None
        else:
            sessions = SessionMetrics(client, verbose=args.verbose)
        while True:
            try:
                if sessions:
                    sessions.update()
                if counts:
                    counts.update()
            except Ice.Exception as e:
                # Connection or session lost: log in again and retry once.
                # A second failure (or a failed login) propagates and exits.
                print(f'Update failed ({type(e).__name__}), reconnecting',
                      file=sys.stderr, flush=True)
                close_quietly(client)
                client = connect(args.host, args.user, args.password)
                g_last_login.set_to_current_time()
                for m in (sessions, counts):
                    if m:
                        m.client = client
                if sessions:
                    sessions.update()
                if counts:
                    counts.update()
            # Sleep for given interval before updating
            sleep(args.interval)
    finally:
        close_quietly(client)
