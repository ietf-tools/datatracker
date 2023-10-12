import os
import scout_apm.celery

from celery import Celery
from scout_apm.api import Config


# Set the default Django settings module for the 'celery' program
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ietf.settings')

app = Celery('ietf')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Turn on Scout APM celery instrumentation if configured in the environment
scout_key = os.environ.get("SCOUT_KEY", "")
scout_name = os.environ.get("SCOUT_NAME", "")
scout_core_agent_socket_path = os.environ.get("SCOUT_CORE_AGENT_SOCKET_PATH", "tcp://scoutapm:6590")
if scout_key and scout_name:
    Config.set(
        key=scout_key,
        name=scout_name,
        monitor=True,
        core_agent_download=False,
        core_agent_launch=False,
        core_agent_path=scout_core_agent_socket_path,
    )
    # Note: Passing the Celery app to install() method as recommended in the
    # Scout documentation causes failure at startup, likely because Scout
    # ingests the config greedily before Django is ready. Have not found a
    # workaround for this other than explicitly configuring Scout.
    scout_apm.celery.install() 

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
