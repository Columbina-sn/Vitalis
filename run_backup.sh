#!/bin/bash
cd /home/ubuntu/Vitalis
source .venv/bin/activate
LOG_FILE="logs/backup_$(date +%Y%m%d).log"
python3 -c "
import asyncio
from tasks import backup_database_task
asyncio.run(backup_database_task())
" >> "$LOG_FILE" 2>&1
echo "备份完成于 $(date)" >> "$LOG_FILE"
find /home/ubuntu/Vitalis/logs -name "backup_*.log" -mtime +21 -delete
