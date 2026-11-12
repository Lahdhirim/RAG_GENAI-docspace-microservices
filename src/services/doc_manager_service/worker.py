import os

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler
from components.parsing_manager import manage_parsing_jobs
from components.scanner import sync_documents
from dotenv import load_dotenv

load_dotenv()

env = os.getenv("ENV", "development")
data_path = "/app/data" if env == "production" else "data"

scheduler = BlockingScheduler(executors={"default": ThreadPoolExecutor(max_workers=1)})


def run_cycle():
    """Synchronize documents with the database, then manage parsing jobs."""
    sync_documents(f"{data_path}/bronze")
    manage_parsing_jobs()


scheduler.add_job(run_cycle, "interval", seconds=20)
scheduler.start()
