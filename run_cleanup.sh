#!/bin/bash
cd /home/ubuntu/Vitalis
source .venv/bin/activate
LOG_FILE="logs/cleanup_$(date +%Y%m%d).log"
python3 -c "
import asyncio
from tasks import cleanup_soft_deleted_records
asyncio.run(cleanup_soft_deleted_records())
" >> "$LOG_FILE" 2>&1
echo "清理任务完成于 $(date)" >> "$LOG_FILE"
find /home/ubuntu/Vitalis/logs -name "cleanup_*.log" -mtime +21 -delete
