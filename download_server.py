#!/usr/bin/env python3
"""文件下载服务。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI()
ARCHIVE_PATH = Path(__file__).resolve().parent / "xhs-auto-agent.tar.gz"


@app.get("/download/xhs-auto-agent.tar.gz")
async def download():
    if ARCHIVE_PATH.exists():
        return FileResponse(
            path=ARCHIVE_PATH,
            filename="xhs-auto-agent.tar.gz",
            media_type="application/gzip",
        )
    return {"error": "文件不存在"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
