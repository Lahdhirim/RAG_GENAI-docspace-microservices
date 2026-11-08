from apscheduler.schedulers.blocking import BlockingScheduler
from components.parsing_jobs import parse_documents, update_parsing_jobs
from components.scanner import sync_documents

scheduler = BlockingScheduler()

# Periodically scan documents and synchronize them with the database
scheduler.add_job(lambda: sync_documents("/app/data"), "interval", seconds=20)

# Submit parsing jobs periodically to the parser_service
scheduler.add_job(lambda: parse_documents("app/silver"), "interval", seconds=20)

# Get updates on parsing jobs periodically from the parser_service
scheduler.add_job(lambda: update_parsing_jobs(), "interval", seconds=10)

# Retrieve documents to parse
scheduler.start()
