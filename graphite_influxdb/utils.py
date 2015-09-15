import datetime
import sys
import re
from .constants import INFLUXDB_AGGREGATIONS

def calculate_interval(start_time, end_time):
    """Calculates wanted data series interval according to start and end times

    Returns interval in seconds
    :param start_time: Start time in seconds from epoch
    :param end_time: End time in seconds from epoch"""
    time_delta = end_time - start_time
    deltas = {
        # # 1 hour -> 1s
        # 3600 : 1,
        # # 1 day -> 30s
        # 86400 : 30,
        # 3 days -> 1min
        259200 : 60,
        # 7 days -> 5min
        604800 : 300,
        # 14 days -> 10min
        1209600 : 600,
        # 28 days -> 15min
        2419200 : 900,
        # 2 months -> 30min
        4838400 : 1800,
        # 4 months -> 1hour
        9676800 : 3600,
        # 12 months -> 3hours
        31536000 : 7200,
        # 4 years -> 12hours
        126144000 : 43200,
        }
    for delta in sorted(deltas.keys()):
        if time_delta <= delta:
            return deltas[delta]
    # 1 day default, or if time range > 4 year
    return 86400

class NullStatsd(object):
    """Fake StatsClient compatible class to use when statsd is not configured"""

    def __enter__(self):
        return self

    def __exit__(self, _type, value, traceback):
        pass

    def timer(self, key, val=None):
        return self

    def timing(self, key, val):
        pass

    def start(self):
        pass

    def stop(self):
        pass

def normalize_config(config):
    cfg = config.get('influxdb', None)
    ret = {}
    if not cfg:
        sys.stderr.write("Missing required 'influxdb' configuration in graphite-api"
                         "config - please update your configuration file to include"
                         "at least 'influxdb: db: <db_name>'\n")
        sys.exit(1)
    ret['host'] = cfg.get('host', 'localhost')
    ret['port'] = cfg.get('port', 8086)
    ret['user'] = cfg.get('user', 'graphite')
    ret['passw'] = cfg.get('pass', 'graphite')
    ret['db'] = cfg.get('db', 'graphite')
    ssl = cfg.get('ssl', False)
    ret['ssl'] = (ssl == 'true')
    ret['schema'] = cfg.get('schema', [])
    ret['log_file'] = cfg.get('log_file', None)
    ret['log_level'] = cfg.get('log_level', 'info')
    if config.get('statsd', None):
        ret['statsd'] = config.get('statsd')
    ret['aggregation_functions'] = _compile_aggregation_patterns(
        cfg.get('aggregation_functions', None))
    return ret

def _compile_aggregation_patterns(aggregation_functions):
    """Compile aggregation function patterns to compiled regex objects"""
    if not aggregation_functions:
        return
    for pattern in aggregation_functions.copy().keys():
        if not aggregation_functions[pattern] in INFLUXDB_AGGREGATIONS:
            sys.stderr.write("Requested aggregation function '%s' is not a valid InfluxDB"
                             "aggregation function - ignoring..\n" % (
                                 aggregation_functions[pattern],))
            del aggregation_functions[pattern]
            continue
        try:
            aggregation_functions[re.compile(r'%s' % (pattern,))] = aggregation_functions[pattern]
        except re.error:
            sys.stderr.write("Error compiling regex pattern '%s' - ignoring..\n" % (
                pattern,))
        del aggregation_functions[pattern]
    return aggregation_functions

def get_aggregation_func(path, aggregation_functions):
    """Lookup aggregation function for path, if any.
    Defaults to 'mean'."""
    if not aggregation_functions:
        return 'mean'
    for pattern in aggregation_functions:
        if pattern.search(path):
            return aggregation_functions[pattern]
    return 'mean'

def read_influxdb_values(influxdb_data):
    """Return generator for values from InfluxDB data"""
    _data = {}
    for key in influxdb_data.keys():
        _data[key[0]] = (d['value'] for d in influxdb_data.get_points(key[0]))
    return _data
