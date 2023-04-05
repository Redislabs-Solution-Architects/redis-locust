from locust import User, HttpUser, task, events
from locust.runners import MasterRunner
import logging
import redis
import time
import random
import string

global myRedis

@events.init_command_line_parser.add_listener
def parse_args(parser):
    """
    Adds customer arguments to Locust
    """
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

class DataLayer():

    def __init__(self, environment):
        self.environment = environment

    def setkey(self,localRedis):

        exception = None
        start_time = time.perf_counter()

        try:
            # Response is not saved in order to keep worker as lightweight as possible
            localRedis.set( \
                ''.join((self.environment.parsed_options.key_name_prefix, str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))), \
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))))
        except Exception as e:
            exception = e

        events.request.fire(
            request_type="redis",
            name="set",
            response_time=(time.perf_counter() - start_time) * 1000 * 1000,
            response_length=0, # No response length is recorded, again to keep worker lightweight
            exception=exception)

    def getkey(self,localRedis):

        exception = None
        start_time = time.perf_counter()

        try:
            # Response is not saved in order to keep worker as lightweight as possible
            localRedis.get( \
                ''.join((self.environment.parsed_options.key_name_prefix, \
                         str(random.randint(1, self.environment.parsed_options.number_of_keys)).zfill(self.environment.parsed_options.key_name_length))))
        except Exception as e:
            exception = e

        events.request.fire(
            request_type="redis",
            name="get",
            response_time=(time.perf_counter() - start_time) * 1000 * 1000,
            response_length=0, # No response length is recorded, again to keep worker lightweight
            exception=exception)

class ReadWrite_4to1(User):

    global myRedis

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(4)
    def getkey(self):
        self.myDataLayer.getkey(myRedis)

    @task(1)
    def setkey(self):
        self.myDataLayer.setkey(myRedis)

class Read_Only(User):

    global myRedis

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(1)
    def getkey(self):
        self.myDataLayer.getkey(myRedis)

class Write_Only(User):

    global myRedis

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(1)
    def setkey(self):
        self.myDataLayer.setkey(myRedis)

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    With the annotation attaching this function to test_start, it will execute on every locust
    process when a test is started (not when the locust process starts, but when an actual test
    in executed.  You can create global resources here that can be used subsequently by individual
    users executing tasks.  In our case we will create a connection to Redis.
    """

    global myRedis

    if isinstance(environment.runner, MasterRunner):
        logging.info("Master node test start")
    else:
        logging.info("Worker or standalone node test start")

        if (environment.parsed_options.cluster in ("Y", "y", "YES", "yes", "true", "TRUE", "True")):
            redisConnection = redis.cluster.RedisCluster
            logging.info("Creating clustered Redis connection")
        else:
            redisConnection = redis.Redis
            logging.info("creating standalone Redis connection")

        myTls = environment.parsed_options.tls in ("Y", "y", "YES", "yes", "true", "TRUE", "True" )

        myRedis = redisConnection(
            host=environment.parsed_options.redis_host,
            port=environment.parsed_options.redis_port,
            username=environment.parsed_options.username,
            password=environment.parsed_options.password,
            ssl=myTls,
            socket_timeout=environment.parsed_options.timeout,
            socket_connect_timeout=environment.parsed_options.timeout)