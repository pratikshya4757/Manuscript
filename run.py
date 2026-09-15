"""Convenience entry point: python run.py"""
import sys

# EasyOCR/other libraries print unicode progress characters; on Windows the
# default console/file codepage (cp1252) can't encode them and crashes the
# process. Force UTF-8 with replacement so a progress bar never takes down
# a request.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
