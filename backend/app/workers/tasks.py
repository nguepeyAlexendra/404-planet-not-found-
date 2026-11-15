from app.services import jobs
from app.workers.celery_app import celery


@celery.task(name="nisar.run_job", bind=True, max_retries=0)
def run_job_task(self, job_id: str) -> None:  # noqa: ARG001
    jobs.run_job(job_id)
