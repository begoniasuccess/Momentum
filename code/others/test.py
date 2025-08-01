import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
# python -u test.py 2>&1 | Tee-Object -FilePath ../log/test.log -Append
