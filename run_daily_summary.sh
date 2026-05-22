#!/bin/bash
cd /home/ubuntu/Vitalis
source .venv/bin/activate
LOG_FILE="logs/daily_summary_$(date +%Y%m%d).log"
python3 -c "
import asyncio
from tasks import daily_summary_task
asyncio.run(daily_summary_task())
" >> "$LOG_FILE" 2>&1
echo "每日摘要完成于 $(date)" >> "$LOG_FILE"
find /home/ubuntu/Vitalis/logs -name "daily_summary_*.log" -mtime +21 -delete
