from apscheduler.schedulers.blocking import BlockingScheduler
from components.scanner import sync_documents

scheduler = BlockingScheduler()
scheduler.add_job(lambda: sync_documents("data/"), "interval", seconds=20)
scheduler.start()