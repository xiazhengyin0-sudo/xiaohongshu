#!/usr/bin/env python3
"""文件下载服务"""
from fastapi import FastAPI
from fastapi.responses import FileResponse
import os

app = FastAPI()

@app.get("/download/xhs-auto-agent.tar.gz")
async def download():
    filepath = "/workspace/xhs-auto-agent.tar.gz"
    if os.path.exists(filepath):
        return FileResponse(
            path=filepath,
            filename="xhs-auto-agent.tar.gz",
            media_type="application/gzip"
        )
    return {"error": "文件不存在"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)
