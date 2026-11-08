from apscheduler.schedulers.blocking import BlockingScheduler
from components.parsing_manager import manage_parsing_jobs
from components.scanner import sync_documents

scheduler = BlockingScheduler()

# Periodically scan documents and synchronize them with the database
scheduler.add_job(lambda: sync_documents("/app/data"), "interval", seconds=20)

# Submit parsing jobs periodically to the parser_service and update their status
scheduler.add_job(lambda: manage_parsing_jobs("app/silver"), "interval", seconds=20)

# Retrieve documents to parse
scheduler.start()
