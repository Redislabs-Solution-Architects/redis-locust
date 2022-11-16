from locust import User, HttpUser, task, events
from locust.runners import MasterRunner
import logging
import redis
import time
import random
import string
import numpy

global myRedis
global myRedisSALocal
global myRedisSARemote

@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--aa_sa_mode", type=str, env_var="RED_LOCUST_AA_SA_MODE", default="BOTH", help="Test mode [BOTH|SA|SA")
    parser.add_argument("--redis_host", type=str, env_var="RED_LOCUST_HOST", default="localhost", help="Host for Redis")
    parser.add_argument("--redis_port", type=str, env_var="RED_LOCUST_PORT", default="6001", help="Port for Redis")
    parser.add_argument("--username", type=str, env_var="RED_LOCUST_USERNAME", default="", help="Username for Redis")
    parser.add_argument("--password", type=str, env_var="RED_LOCUST_PASSWORD", default="", help="Password for Redis")
    parser.add_argument("--redis_host_sa_local", type=str, env_var="RED_LOCUST_HOST_SA_LOCAL", default="localhost", help="Host for SA Local Redis")
    parser.add_argument("--redis_port_sa_local", type=str, env_var="RED_LOCUST_PORT_SA_LOCAL", default="6002", help="Port for SA Local Redis")
    parser.add_argument("--username_sa_local", type=str, env_var="RED_LOCUST_USERNAME_SA_LOCAL", default="", help="Username for SA Local Redis")
    parser.add_argument("--password_sa_local", type=str, env_var="RED_LOCUST_PASSWORD_SA_LOCAL", default="", help="Password for SA Local Redis")
    parser.add_argument("--redis_host_sa_remote", type=str, env_var="RED_LOCUST_HOST_SA_REMOTE", default="localhost", help="Host for SA Remote Redis")
    parser.add_argument("--redis_port_sa_remote", type=str, env_var="RED_LOCUST_PORT_SA_REMOTE", default="6003", help="Port for SA Remote Redis")
    parser.add_argument("--username_sa_remote", type=str, env_var="RED_LOCUST_USERNAME_SA_REMOTE", default="", help="Username SA Remote for Redis")
    parser.add_argument("--password_sa_remote", type=str, env_var="RED_LOCUST_PASSWORD_SA_REMOTE", default="", help="Password SA Remote for Redis")
    parser.add_argument("--timeout", type=int, env_var="RED_LOCUST_TIMEOUT", default=500, help="Timeout for Redis in ms")
    parser.add_argument("--cluster", type=str, env_var="RED_LOCUST_CLUSTER", default="N", help="Cluster mode (Y/N)")
    parser.add_argument("--tls", type=str, env_var="RED_LOCUST_TLS", default="N", help="TLS (Y/N)")
    parser.add_argument("--key_name_prefix", type=str, env_var="RED_LOCUST_KEY_NAME_PREFIX", default="rloc:", help="Prefix for key names")
    parser.add_argument("--key_name_length", type=int, env_var="RED_LOCUST_KEY_NAME_LENGTH", default=20, help="Length (ie digits) of key name (not including prefix)")
    parser.add_argument("--number_of_keys", type=int, env_var="RED_LOCUST_NUM_OF_KEYS", default=1000000, help="Number of keys")
    parser.add_argument("--value_min_chars", type=int, env_var="RED_LOCUST_VALUE_MIN_BYTES", default=15, help="Minimum characters to store in key value")
    parser.add_argument("--value_max_chars", type=int, env_var="RED_LOCUST_VALUE_MAX_BYTES", default=15, help="Maximum characters to store in key value")
    parser.add_argument("--zipf_shape", type=float, env_var="RED_LOCUST_ZIPF_SHAPE", default=1.01, help="Zipf shape")
    parser.add_argument("--zipf_direction", type=int, env_var="RED_LOCUST_ZIPF_DIRECTION", default=1, help="Zipf direction [1|-1]")
    parser.add_argument("--zipf_max_keys", type=int, env_var="RED_LOCUST_ZIPF_MAX_KEYS", default=10000000, help="Zipf max keys")
    parser.add_argument("--zipf_offset", type=int, env_var="RED_LOCUST_ZIPF_OFFSET", default=0, help="Zipf Offset")
    parser.add_argument("--zrem_seconds", type=int, env_var="RED_LOCUST_ZREM_SECONDS", default=300, help="Seconds to keep when trimming zsets")
    parser.add_argument("--pipeline_size", type=int, env_var="RED_LOCUST_PIPELINE_SIZE", default=100, help="Commands per Redis pipeline")
    parser.add_argument("--zcount_seconds", type=int, env_var="RED_LOCUST_ZCOUNT_SECONDS", default=150, help="Number of seconds to query for zcount")
    parser.add_argument("--jumbo_frequency", type=int, env_var="RED_LOCUST_JUMBO_FREQUENCY", default=50, help="Frequency of jumbo zadd logic")
    parser.add_argument("--jumbo_initial_exclude", type=int, env_var="RED_LOCUST_JUMBO_INITIAL_EXCLUDE", default=100, help="Number of initial keys to exclude from jumbo logic")
    parser.add_argument("--jumbo_size", type=str, env_var="RED_LOCUST_JUMBO_SIZE", default="25,25,50,100,1000", help="Array representing the extra members for jumbo zadds")
    parser.add_argument("--version_display", type=str, env_var="RED_VERSION_DISPLAY", default="0.2", help="Just used to show locust file version in UI")

class DataLayer():

    def __init__(self, environment):
        self.environment = environment

    def get_key_int(self):
        """
        Function to generate pick integer to use for creation of key name(s)
        Implements zipf distribution, with shape, direction, and offset controlled by locust params
        """

        x = self.environment.parsed_options.zipf_max_keys + 1
        while x > self.environment.parsed_options.zipf_max_keys:
            x = numpy.random.zipf(a=self.environment.parsed_options.zipf_shape, size=1)[0]

        return(self.environment.parsed_options.zipf_offset + (x * self.environment.parsed_options.zipf_direction))

    def get_key_name_from_int(self, key_int):
        """
        Function to generate a key name string from an integer
        Implements zero filling based on locust parameter
        """

        return(''.join((self.environment.parsed_options.key_name_prefix, str(key_int).zfill(self.environment.parsed_options.key_name_length))))

    def record_request_meta(self, request_type, name, start_time, end_time, response_length, response, exception):
        """
        Function to record locust request, based on standard locust request meta data
        repsonse time is calculated form inputs and is expressed in microseconds
        """

        request_meta = {
            "request_type": request_type,
            "name": name,
            "start_time": start_time,
            "response_time": (time.perf_counter() - start_time) * 1000 * 1000,
            "response_length": response_length,
            "response": response,
            "context": {},
            "exception": exception }

        if exception:
            events.request_failure.fire(**request_meta)
        else:
            events.request_success.fire(**request_meta)

    def zcount(self,localRedis, SALocalRedis):
        """
        Function to count items in a Redis sorted Set.
        Will count against active-active setup and stand-alone setup, recording requests to locust.
        """

        # Prepare data for below sections
        transtime = time.time()
        keyint = self.get_key_int()
        keyname = self.get_key_name_from_int(keyint)

        # Active-Active section
        if (self.environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = localRedis.zcount(
                    keyname,
                    transtime-self.environment.parsed_options.zcount_seconds, transtime)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "aa",
                name = "zcount",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Stand-alone section
        if (self.environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = SALocalRedis.zcount(
                    keyname,
                    transtime-self.environment.parsed_options.zcount_seconds,
                    transtime)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-local",
                name = "zcount",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

    def zcount_pipeline(self,localRedis,SALocalRedis):
        """
        Function to count items in a Redis sorted Set. Run as a pipeline with number of commands
        in pipeline controlled by locust parameter.
        Will count against active-active setup and stand-alone setup, recording requests to locust.
        """

        # Prepare data for sections below
        transtime = time.time()
        keyintlist = []
        for i in range(self.environment.parsed_options.pipeline_size):
            keyint = self.get_key_int()
            keyintlist.append(keyint)

        ## Active-Active section
        if (self.environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
            myResponse = None
            myException = None
            try:
                p = localRedis.pipeline(transaction=False)
                for i in keyintlist:
                    r = p.zcount(
                        self.get_key_name_from_int(i),
                        transtime-self.environment.parsed_options.zcount_seconds, transtime)

                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "aa",
                name = "zcount_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Stand-alone section
        if (self.environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
            myResponse = None
            myException = None
            try:
                p = SALocalRedis.pipeline(transaction=False)

                for keyint in keyintlist:
                    r = p.zcount(
                        self.get_key_name_from_int(keyint),
                        transtime-self.environment.parsed_options.zcount_seconds, transtime)

                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-local",
                name = "zcount_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

    def zaddandrem(self,localRedis, SALocalRedis, SARemoteRedis):
        """
        Function that will add recent transactions to sorted set, and then delete older transactions from the same sorted set.  Will
        pick keys for actions and implements jumbo adds according to locust parameters.
        Functions against active-active Redis and against a pair of stand-alone Redis instances, sending writes to all three locations.
        """

        # Build keys and member logic for use in later Redis commands
        baseRequestName = "zadd"
        keyint = self.get_key_int()
        transtime = time.time()

        members = {''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))): time.time()}

        orig_keyint = (keyint - self.environment.parsed_options.zipf_offset ) * self.environment.parsed_options.zipf_direction
        if ((orig_keyint > self.environment.parsed_options.jumbo_initial_exclude)  and (keyint % self.environment.parsed_options.jumbo_frequency == 0) ):
            baseRequestName = "zadd_jumbo"
            count = int(random.choice(self.environment.parsed_options.jumbo_size.split(',')))
            for i in range(count):
                members.update( {''.join(str(i)).join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))): time.time()})

        # Active-active zadd section
        if (self.environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = localRedis.zadd(
                    self.get_key_name_from_int(keyint),
                    members)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "aa",
                name = baseRequestName,
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Local stand-alone zadd section
        if (self.environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = SALocalRedis.zadd(
                    self.get_key_name_from_int(keyint),
                    members)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-local",
                name = baseRequestName,
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

            # Remote stand-alone zadd section
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = SARemoteRedis.zadd(
                    self.get_key_name_from_int(keyint),
                    members)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-remote",
                name = baseRequestName,
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        if (self.environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
            # Active-active zrem section
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = localRedis.zremrangebyscore( \
                    ''.join((self.environment.parsed_options.key_name_prefix, str(keyint).zfill(self.environment.parsed_options.key_name_length))), \
                    0, transtime - self.environment.parsed_options.zrem_seconds)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "aa",
                name = "zrem",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Local stand-alone zrem section
        if (self.environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = SALocalRedis.zremrangebyscore( \
                    ''.join((self.environment.parsed_options.key_name_prefix, str(keyint).zfill(self.environment.parsed_options.key_name_length))), \
                    0, transtime - self.environment.parsed_options.zrem_seconds)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-local",
                name = "zrem",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

            # Remote stand-alone zrem section
            myResponse = None
            myException = None
            trans_start_time = time.perf_counter()
            try:
                myResponse = SARemoteRedis.zremrangebyscore( \
                    ''.join((self.environment.parsed_options.key_name_prefix, str(keyint).zfill(self.environment.parsed_options.key_name_length))), \
                    0, transtime - self.environment.parsed_options.zrem_seconds)
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-remote",
                name = "zrem",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

    def zaddandrem_pipeline(self,localRedis, SALocalRedis, SARemoteRedis):
        """
        Function that will add recent transactions to sorted set, and then delete older transactions from the same sorted set.
        Will execute commands in a pipeline, with number of commands per pipe controlled by locust parameter.
        Will pick keys for actions and implements jumbo adds according to locust parameters.
        Functions against active-active Redis and against a pair of stand-alone Redis instances, sending writes to all three locations.
        """

        # Build keys and members for use in all sections
        keyname_and_members_list = []
        transtime = time.time()

        for i in range(self.environment.parsed_options.pipeline_size-1):
            keyint = self.get_key_int()
            members = {''.join(random.choices(string.ascii_uppercase + string.digits, k=random.randint(self.environment.parsed_options.value_min_chars, self.environment.parsed_options.value_max_chars))): time.time()}

            orig_keyint = (keyint * self.environment.parsed_options.zipf_direction) - self.environment.parsed_options.zipf_offset
            if ((orig_keyint > self.environment.parsed_options.jumbo_initial_exclude)  and (keyint % self.environment.parsed_options.jumbo_frequency == 0) ):
                count = int(random.choice(self.environment.parsed_options.jumbo_size.split(',')))
                for i in range(count):
                    members.update(
                        {''.join(str(i)).join(random.choices(string.ascii_uppercase + string.digits,
                                                             k=random.randint(self.environment.parsed_options.value_min_chars,
                                                                              self.environment.parsed_options.value_max_chars))): time.time()})
            keyname_and_members_list.append((self.get_key_name_from_int(keyint), members))

        # Active-active zadd section
        if (self.environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
            myResponse = None
            myException = None
            try:
                p = localRedis.pipeline(transaction=False)
                for i in keyname_and_members_list:
                    r = p.zadd(i[0], i[1])
                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "aa",
                name = "zadd_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Local stand-alone zadd section
        if (self.environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
            myResponse = None
            myException = None
            try:
                p = SALocalRedis.pipeline(transaction=False)
                for i in keyname_and_members_list:
                    r = p.zadd(i[0], i[1])
                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-local",
                name = "zadd_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

            # Remote stand-alone zadd section
            myResponse = None
            myException = None
            try:
                p = SARemoteRedis.pipeline(transaction=False)
                for i in keyname_and_members_list:
                    r = p.zadd(i[0], i[1])
                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-remote",
                name = "zadd_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Active-active zrem section
        if (self.environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
            myResponse = None
            myException = None
            try:
                p = localRedis.pipeline(transaction=False)
                for i in keyname_and_members_list:
                    r = p.zremrangebyscore(i[0], 0, transtime - self.environment.parsed_options.zrem_seconds)
                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "aa",
                name = "zrem_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

        # Local stand-alone zrem section
        if (self.environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
            myResponse = None
            myException = None
            try:
                p = SALocalRedis.pipeline(transaction=False)
                for i in keyname_and_members_list:
                    r = p.zremrangebyscore(i[0], 0, transtime - self.environment.parsed_options.zrem_seconds)
                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-local",
                name = "zrem_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

            # Remote zrem section
            myResponse = None
            myException = None
            try:
                p = SARemoteRedis.pipeline(transaction=False)
                for i in keyname_and_members_list:
                    r = p.zremrangebyscore(i[0], 0, transtime - self.environment.parsed_options.zrem_seconds)
                trans_start_time = time.perf_counter()
                myResponse = p.execute();
            except Exception as e:
                myException = e

            self.record_request_meta(
                request_type = "sa-remote",
                name = "zrem_pipe",
                start_time = trans_start_time,
                end_time = time.perf_counter(),
                response_length = 0,
                response = myResponse,
                exception = myException)

class RedisUser(User):
    """
    Locust user class that defines tasks and weights for test runs.
    """

    global myRedis
    global myRedisSALocal
    global myRedisSARemote

    def on_start(self):
        self.myDataLayer = DataLayer(self.environment)

    @task(1)
    def zcount_pipeline(self):
        self.myDataLayer.zcount_pipeline(myRedis, myRedisSALocal)

    @task(1)
    def zaddandrem(self):
        self.myDataLayer.zaddandrem(myRedis, myRedisSALocal, myRedisSARemote)

    @task(1)
    def zaddandrem_pipeline(self):
        self.myDataLayer.zaddandrem_pipeline(myRedis, myRedisSALocal, myRedisSARemote)

    @task(1)
    def zcount(self):
        self.myDataLayer.zcount(myRedis, myRedisSALocal)

@events.test_start.add_listener
def _(environment, **kw):
    """
    Function tagged in locust just to log some information on start-up
    """
    logging.info("Locust parameters for test run")
    logging.info((vars(environment.parsed_options)))

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Function to initialize Redis connections on startup of locust workers.
    """
    global myRedis
    global myRedisSALocal
    global myRedisSARemote

    if isinstance(environment.runner, MasterRunner):
        logging.info("Locust master node test start")
    else:
        logging.info("Locust worker or stand-alone node test start")
        if (environment.parsed_options.cluster == "Y"):
            if (environment.parsed_options.tls == "Y"):
                myTls = True
            else:
                myTls = False
            if (environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
                myRedis = redis.cluster.RedisCluster(
                    host=environment.parsed_options.redis_host,
                    port=environment.parsed_options.redis_port,
                    username=environment.parsed_options.username,
                    password=environment.parsed_options.password,
                    ssl=myTls,
                    socket_timeout=environment.parsed_options.timeout,
                    socket_connect_timeout=environment.parsed_options.timeout)
            else:
                myRedis = None
            if (environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
                myRedisSALocal = redis.cluster.RedisCluster(
                    host=environment.parsed_options.redis_host_sa_local,
                    port=environment.parsed_options.redis_port_sa_local,
                    username=environment.parsed_options.username_sa_local,
                    password=environment.parsed_options.password_sa_local,
                    ssl=myTls,
                    socket_timeout=environment.parsed_options.timeout,
                    socket_connect_timeout=environment.parsed_options.timeout)
                myRedisSARemote = redis.cluster.RedisCluster(
                    host=environment.parsed_options.redis_host_sa_remote,
                    port=environment.parsed_options.redis_port_sa_remote,
                    username=environment.parsed_options.username_sa_remote,
                    password=environment.parsed_options.password_sa_remote,
                    ssl=myTls,
                    socket_timeout=environment.parsed_options.timeout,
                    socket_connect_timeout=environment.parsed_options.timeout)
            else:
                myRedisSALocal = None
                myRedisSARemote = None
        else:
            if (environment.parsed_options.tls == "Y"):
                myTls = True
            else:
                myTls = False
            if (environment.parsed_options.aa_sa_mode in ['AA', 'BOTH'] ):
                myRedis = redis.Redis(
                    host=environment.parsed_options.redis_host,
                    port=environment.parsed_options.redis_port,
                    username=environment.parsed_options.username,
                    password=environment.parsed_options.password,
                    ssl=myTls,
                    socket_timeout=environment.parsed_options.timeout,
                    socket_connect_timeout=environment.parsed_options.timeout)
            else:
                myRedis = None
            if (environment.parsed_options.aa_sa_mode in ['SA', 'BOTH'] ):
                myRedisSALocal = redis.Redis(
                    host=environment.parsed_options.redis_host_sa_local,
                    port=environment.parsed_options.redis_port_sa_local,
                    username=environment.parsed_options.username_sa_local,
                    password=environment.parsed_options.password_sa_local,
                    ssl=myTls,
                    socket_timeout=environment.parsed_options.timeout,
                    socket_connect_timeout=environment.parsed_options.timeout)
                myRedisSARemote = redis.Redis(
                    host=environment.parsed_options.redis_host_sa_remote,
                    port=environment.parsed_options.redis_port_sa_remote,
                    username=environment.parsed_options.username_sa_remote,
                    password=environment.parsed_options.password_sa_remote,
                    ssl=myTls,
                    socket_timeout=environment.parsed_options.timeout,
                    socket_connect_timeout=environment.parsed_options.timeout)
            else:
                myRedisSALocal = None
                myRedisSARemote = None