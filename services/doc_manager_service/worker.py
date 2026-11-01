from apscheduler.schedulers.blocking import BlockingScheduler
from components.scanner import scan_documents

scheduler = BlockingScheduler()
scheduler.add_job(lambda: scan_documents("data/"), "interval", minutes=1)
scheduler.start()