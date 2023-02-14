from locust import User, HttpUser, task, events
from locust.runners import MasterRunner
import logging
import redis
import time
import random
import string

global myRedis

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--redis_host", type=str, env_var="RED_LOCUST_HOST", default="localhost", help="Host for Redis")
    parser.add_argument("--redis_port", type=int, env_var="RED_LOCUST_PORT", default=6379, help="Port for Redis")
    parser.add_argument("--username", type=str, env_var="RED_LOCUST_USERNAME", default="", help="Username for Redis")
    parser.add_argument("--password", type=str, env_var="RED_LOCUST_PASSWORD", default="", help="Password for Redis")
    parser.add_argument("--timeout", type=int, env_var="RED_LOCUST_TIMEOUT", default=500, help="Timeout for Redis in ms")
    parser.add_argument("--cluster", type=str, env_var="RED_LOCUST_CLUSTER", default="N", help="Cluster mode (Y/N)")
    parser.add_argument("--tls", type=str, env_var="RED_LOCUST_TLS", default="N", help="TLS (Y/N)")
    parser.add_argument("--key_name_prefix", type=str, env_var="RED_LOCUST_KEY_NAME_PREFIX", default="rloc:", help="Prefix for key names")
    parser.add_argument("--key_name_length", type=int, env_var="RED_LOCUST_KEY_NAME_LENGTH", default=10, help="Length (ie digits) of key name (not including prefix)")
    parser.add_argument("--number_of_keys", type=int, env_var="RED_LOCUST_NUM_OF_KEYS", default=1000000, help="Number of keys")
    parser.add_argument("--value_min_chars", type=int, env_var="RED_LOCUST_VALUE_MIN_BYTES", default=8, help="Minimum characters to store in key value")
    parser.add_argument("--value_max_chars", type=int, env_var="RED_LOCUST_VALUE_MAX_BYTES", default=8, help="Maximum characters to store in key value")
    parser.add_argument("--version_display", type=str, env_var="RED_VERSION_DISPLAY", default="0.2", help="Just used to show locust file version in UI")

@events.test_start.add_listener
def _(environment, **kw):
    print(f"Custom argument supplied: {environment.parsed_options.redis_host}")
    print(f"Custom argument supplied: {environment.parsed_options.redis_port}")
    print(f"Custom argument supplied: {environment.parsed_options.username}")
    print(f"Custom argument supplied: {environment.parsed_options.timeout}")
    print(f"Custom argument supplied: {environment.parsed_options.cluster}")

class DataLayer():

    def __init__(self, environment):
        self.environment = environment

    def setkey(self,localRedis):
        request_meta = {
            "request_type": "redis",
            "name": "set",
            "start_time": time.time(),
            "response_length": 0,  # calculating this for an xmlrpc.client response would be too hard
            "response": None,
            "context": {},  # see HttpUser if you actually want to implement contexts
            "exception": None }

        start_perf_counter = time.perf_counter()
        try:
            request_meta["response"] = localRedis.set( \
                ''.join((self.environment.parsed_options.key_name_prefix, str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))), \
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))))
        except Exception as e:
            request_meta["exception"] = e

        request_meta["response_time"] = (time.perf_counter() - start_perf_counter) * 1000 * 1000
        if request_meta["exception"] :
            events.request_failure.fire(**request_meta)
        else:
            events.request_success.fire(**request_meta)

    def getkey(self,localRedis):
        request_meta = {
            "request_type": "redis",
            "name": "get",
            "start_time": time.time(),
            "response_length": 0,  # calculating this for an xmlrpc.client response would be too hard
            "response": None,
            "context": {},  # see HttpUser if you actually want to implement contexts
            "exception": None }
        start_perf_counter = time.perf_counter()
        try:
            request_meta["response"] = localRedis.get( \
                ''.join((self.environment.parsed_options.key_name_prefix, \
                         str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))))
        except Exception as e:
            request_meta["exception"] = e

        request_meta["response_time"] = (time.perf_counter() - start_perf_counter) * 1000 * 1000
        if request_meta["exception"] :
            events.request_failure.fire(**request_meta)
        else:
            events.request_success.fire(**request_meta)

    def setkey_pipeline(self,localRedis):
        request_meta = {
            "request_type": "redis",
            "name": "set_pipeline",
            "start_time": time.time(),
            "response_length": 0,  # calculating this for an xmlrpc.client response would be too hard
            "response": None,
            "context": {},  # see HttpUser if you actually want to implement contexts
            "exception": None }

        try:
            p = localRedis.pipeline(transaction=False)
            for i in range(25-1):
                r = p.set( \
                    ''.join((self.environment.parsed_options.key_name_prefix, str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))), \
                    ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))))

            # Capture response time only for final item in pipeline (and the execute)
            start_perf_counter = time.perf_counter()
            r = p.set( \
                ''.join((self.environment.parsed_options.key_name_prefix, str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))), \
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))))
            request_meta["response"] = p.execute();

        except Exception as e:
            request_meta["exception"] = e

        request_meta["response_time"] = (time.perf_counter() - start_perf_counter) * 1000 * 1000
        if request_meta["exception"] :
            events.request_failure.fire(**request_meta)
        else:
            events.request_success.fire(**request_meta)

    def getkey_pipeline(self,localRedis):
        request_meta = {
            "request_type": "redis",
            "name": "get_pipeline",
            "start_time": time.time(),
            "response_length": 0,  # calculating this for an xmlrpc.client response would be too hard
            "response": None,
            "context": {},  # see HttpUser if you actually want to implement contexts
            "exception": None }
        try:
            p = localRedis.pipeline(transaction=False)
            for i in range(25-1):
                r = p.get( \
                    ''.join((self.environment.parsed_options.key_name_prefix, \
                             str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))))

            # Capture response time only for final item in pipeline (and the execute)
            start_perf_counter = time.perf_counter()
            r = p.get( \
                ''.join((self.environment.parsed_options.key_name_prefix, \
                         str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))))
            request_meta["response"] = p.execute();

        except Exception as e:
            request_meta["exception"] = e

        request_meta["response_time"] = (time.perf_counter() - start_perf_counter) * 1000 * 1000
        if request_meta["exception"] :
            events.request_failure.fire(**request_meta)
        else:
            events.request_success.fire(**request_meta)

class RedisUser(User):

    global myRedis

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(32)
    def getkey(self):
        self.myDataLayer.getkey(myRedis)

    @task(8)
    def setkey(self):
        self.myDataLayer.setkey(myRedis)

    @task(4)
    def getkey_pipeline(self):
        self.myDataLayer.getkey_pipeline(myRedis)

    @task(1)
    def setkey_pipeline(self):
        self.myDataLayer.setkey_pipeline(myRedis)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    global myRedis

    if isinstance(environment.runner, MasterRunner):
        logging.info("Master node test start")
    else:
        logging.info("Worker or standalone node test start")
        if (environment.parsed_options.cluster == "Y"):
            logging.info("Creating clustered Redis connection")
            if (environment.parsed_options.tls == "Y"):
                myTls = True
            else:
                myTls = False
            myRedis = redis.cluster.RedisCluster( \
                host=environment.parsed_options.redis_host, \
                port=environment.parsed_options.redis_port, \
                username=environment.parsed_options.username, \
                password=environment.parsed_options.password, \
                ssl=myTls, \
                socket_timeout=environment.parsed_options.timeout, \
                socket_connect_timeout=environment.parsed_options.timeout)
        else:
            logging.info("creating standalone Redis connection")
            if (environment.parsed_options.tls == "Y"):
                myTls = True
            else:
                myTls = False
            myRedis = redis.Redis( \
                host=environment.parsed_options.redis_host, \
                port=environment.parsed_options.redis_port, \
                username=environment.parsed_options.username, \
                password=environment.parsed_options.password, \
                ssl=myTls, \
                socket_timeout=environment.parsed_options.timeout, \
                socket_connect_timeout=environment.parsed_options.timeout)