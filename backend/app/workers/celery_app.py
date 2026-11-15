from celery import Celery

from app.core.config import get_settings

s = get_settings()
celery = Celery("nisar_vision", broker=s.redis_url, backend=s.redis_url, include=["app.workers.tasks"])
celery.conf.update(task_always_eager=s.celery_always_eager, task_eager_propagates=False, task_acks_late=True,
                   task_time_limit=900, task_soft_time_limit=840, worker_prefetch_multiplier=1,
                   broker_connection_retry_on_startup=True)
