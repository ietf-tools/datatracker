# Copyright The IETF Trust 2024-2025, All Rights Reserved

import os
import ietf
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.pymemcache import PymemcacheInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure security scheme headers for forwarded requests. Cloudflare sets X-Forwarded-Proto 
# for us. Don't trust any of the other similar headers. Only trust the header if it's coming
# from localhost, as all legitimate traffic will reach gunicorn via co-located nginx.
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}
forwarded_allow_ips = "127.0.0.1, ::1"  # this is the default 

# Log as JSON on stdout (to distinguish from Django's logs on stderr)
#
# This is applied as an update to gunicorn's glogging.CONFIG_DEFAULTS.
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
            "qualname": "gunicorn.error",
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["access_console"],
            "propagate": False,
            "qualname": "gunicorn.access",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
        "access_console": {
            "class": "logging.StreamHandler",
            "formatter": "access_json",
            "stream": "ext://sys.stdout",
        },
    },
    "formatters": {
        "json": {
            "class": "ietf.utils.jsonlogger.DatatrackerJsonFormatter",
            "style": "{",
            "format": "{asctime}{levelname}{message}{name}{process}",
        },
        "access_json": {
            "class": "ietf.utils.jsonlogger.GunicornRequestJsonFormatter",
            "style": "{",
            "format": "{asctime}{levelname}{message}{name}{process}",
        },
    },
}

# Track in-flight requests and emit a list of what was happeningwhen a worker is terminated.
# For the default sync worker, there will only be one request per PID, but allow for the
# possibility of multiple requests in case we switch to a different worker class.
#
# This dict is only visible within a single worker, but key by pid to guarantee no conflicts.
#
# Use a list rather than a set to allow for the possibility of overlapping identical requests.
in_flight_by_pid: dict[str, list[str]] = {}  # pid -> list of in-flight requests


def _describe_request(req):
    """Generate a consistent description of a request

    The return value is used identify in-flight requests, so it must not vary between the
    start and end of handling a request. E.g., do not include a timestamp.
    """
    client_ip = "-"
    asn = "-"
    cf_ray = "-"
    for header, value in req.headers:
        header = header.lower()
        if header == "cf-connecting-ip":
            client_ip = value
        elif header == "x-ip-src-asnum":
            asn = value
        elif header == "cf-ray":
            cf_ray = value
    if req.query:
        path = f"{req.path}?{req.query}"
    else:
        path = req.path
    return f"{req.method} {path} (client_ip={client_ip}, asn={asn}, cf_ray={cf_ray})"


def pre_request(worker, req):
    """Log the start of a request and add it to the in-flight list"""
    request_description = _describe_request(req)
    worker.log.info(f"gunicorn starting to process {request_description}")
    in_flight = in_flight_by_pid.setdefault(worker.pid, [])
    in_flight.append(request_description)


def worker_abort(worker):
    """Emit an error log if any requests were in-flight"""
    in_flight = in_flight_by_pid.get(worker.pid, [])
    if len(in_flight) > 0:
        worker.log.error(
            f"Aborted worker {worker.pid} with in-flight requests: {', '.join(in_flight)}"
        )


def worker_int(worker):
    """Emit an error log if any requests were in-flight"""
    in_flight = in_flight_by_pid.get(worker.pid, [])
    if len(in_flight) > 0:
        worker.log.error(
            f"Interrupted worker {worker.pid} with in-flight requests: {', '.join(in_flight)}"
        )


def post_request(worker, req, environ, resp):
    """Remove request from in-flight list when we finish handling it"""
    request_description = _describe_request(req)
    in_flight = in_flight_by_pid.get(worker.pid, [])
    if request_description in in_flight:
        in_flight.remove(request_description)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

    # Setting DATATRACKER_OPENTELEMETRY_ENABLE=all in the environment will enable all
    # opentelemetry instrumentations. Individual instrumentations can be selected by
    # using a space-separated list. See the code below for available instrumentations.
    telemetry_env = os.environ.get("DATATRACKER_OPENTELEMETRY_ENABLE", "").strip()
    if telemetry_env != "":
        enabled_telemetry = [tok.strip().lower() for tok in telemetry_env.split()]
        resource = Resource.create(attributes={
            "service.name": "datatracker",
            "service.version": ietf.__version__,
            "service.instance.id": worker.pid,
            "service.namespace": "datatracker",
            "deployment.environment.name": os.environ.get("DATATRACKER_SERVICE_ENV", "dev")
        })
        trace.set_tracer_provider(TracerProvider(resource=resource))
        otlp_exporter = OTLPSpanExporter(endpoint="https://heimdall-otlp.ietf.org/v1/traces")
    
        trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
    
        # Instrumentations
        if "all" in enabled_telemetry or "django" in enabled_telemetry: 
            DjangoInstrumentor().instrument()
        if "all" in enabled_telemetry or "psycopg2" in enabled_telemetry: 
            Psycopg2Instrumentor().instrument()
        if "all" in enabled_telemetry or "pymemcache" in enabled_telemetry: 
            PymemcacheInstrumentor().instrument()
        if "all" in enabled_telemetry or "requests" in enabled_telemetry: 
            RequestsInstrumentor().instrument()
