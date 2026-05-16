"""
数据采集服务 - 通过 MCP 协议采集小红书数据。

服务对 MCP 调用错误做了显式透传，并提供登录二维码、登录状态、热点采集和定时采集接口。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060/mcp")
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", "3600"))


class XHSMCPClient:
    """小红书 MCP JSON-RPC 客户端。"""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.request_id = 0

    async def call_tool(self, tool_name: str, arguments: Optional[dict] = None) -> Dict[str, Any]:
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments or {}},
            "id": self.request_id,
        }
        try:
            response = await self.client.post(self.base_url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            return {"error": f"MCP 请求失败: {exc}"}

        if "error" in result:
            return {"error": result["error"]}
        return result.get("result", {}) or {}

    async def check_login(self) -> bool:
        result = await self.call_tool("check_login_status")
        return bool(result.get("logged_in") or result.get("is_logged_in") or result.get("status") == "logged_in")

    async def get_login_qrcode(self) -> Dict[str, Any]:
        return await self.call_tool("get_login_qrcode")

    async def get_user_profile(self, user_id: str, xsec_token: Optional[str] = None) -> Dict[str, Any]:
        args = {"user_id": user_id}
        if xsec_token:
            args["xsec_token"] = xsec_token
        return await self.call_tool("user_profile", args)

    async def get_feed_detail(self, feed_id: str, xsec_token: Optional[str] = None) -> Dict[str, Any]:
        args = {"feed_id": feed_id}
        if xsec_token:
            args["xsec_token"] = xsec_token
        return await self.call_tool("get_feed_detail", args)

    async def search_feeds(self, keyword: str, **filters: Any) -> Dict[str, Any]:
        return await self.call_tool("search_feeds", {"keyword": keyword, **filters})

    async def list_feeds(self) -> Dict[str, Any]:
        return await self.call_tool("list_feeds")


class DataCollector:
    """数据采集器。"""

    def __init__(self):
        self.mcp_client = XHSMCPClient(XHS_MCP_URL)
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def collect_account_data(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        logged_in = await self.mcp_client.check_login()
        if not logged_in:
            qrcode = await self.mcp_client.get_login_qrcode()
            return {
                "status": "need_login",
                "qrcode": qrcode.get("qr_code_base64") or qrcode.get("qrcode") or qrcode.get("image"),
                "raw": qrcode,
                "message": "请扫描二维码登录",
            }

        if user_id:
            profile = await self.mcp_client.get_user_profile(user_id)
            return {"status": "success", "data": {"profile": profile, "collected_at": datetime.now().isoformat()}}

        return {"status": "success", "message": "已登录，准备采集"}

    async def collect_feed_data(self, feed_ids: List[str]) -> List[Dict[str, Any]]:
        results = []
        for feed_id in feed_ids:
            detail = await self.mcp_client.get_feed_detail(feed_id)
            results.append({"feed_id": feed_id, "data": detail, "collected_at": datetime.now().isoformat()})
            await asyncio.sleep(1)
        return results

    async def collect_hot_topics(self, keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        search_keywords = keywords or ["职场干货", "穿搭分享", "美食探店", "护肤心得", "居家好物", "旅行攻略"]
        results: Dict[str, Any] = {}
        for keyword in search_keywords[:20]:
            results[keyword] = await self.mcp_client.search_feeds(keyword)
            await asyncio.sleep(2)
        self._save_data("hot_topics.json", results)
        return results

    async def collect_trending_feeds(self) -> Dict[str, Any]:
        feeds = await self.mcp_client.list_feeds()
        self._save_data("trending_feeds.json", feeds)
        return feeds

    def _save_data(self, filename: str, data: Dict[str, Any]) -> None:
        filepath = DATA_DIR / filename
        with filepath.open("w", encoding="utf-8") as f:
            json.dump({"data": data, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

    async def run_scheduled_collection(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        while self.is_running:
            try:
                await self.collect_hot_topics()
                await self.collect_trending_feeds()
            except Exception as exc:
                self._save_data("last_error.json", {"error": str(exc)})
            await asyncio.sleep(COLLECT_INTERVAL)

    def start(self, background_tasks: BackgroundTasks) -> bool:
        if self.is_running:
            return False
        background_tasks.add_task(self.run_scheduled_collection)
        return True

    def stop(self) -> None:
        self.is_running = False


app = FastAPI(title="小红书数据采集服务", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
collector = DataCollector()


class CollectRequest(BaseModel):
    feed_ids: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    user_id: Optional[str] = None


class PublishRequest(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    image_paths: Optional[List[str]] = None
    tags: Optional[List[str]] = None


@app.get("/")
async def root():
    return {"service": "小红书数据采集服务", "version": "1.1.0", "status": "running"}


@app.get("/health")
async def health():
    logged_in = await collector.mcp_client.check_login()
    return {"status": "healthy", "xhs_logged_in": logged_in, "mcp_url": XHS_MCP_URL}


@app.get("/login/status")
async def login_status():
    return {"logged_in": await collector.mcp_client.check_login()}


@app.get("/login/qrcode")
async def login_qrcode():
    result = await collector.mcp_client.get_login_qrcode()
    return {"success": "error" not in result, "data": result}


@app.post("/collect/account")
async def collect_account(request: CollectRequest):
    return await collector.collect_account_data(request.user_id)


@app.post("/collect/feeds")
async def collect_feeds(request: CollectRequest):
    if not request.feed_ids:
        return {"success": False, "error": "请提供 feed_ids"}
    return {"success": True, "data": await collector.collect_feed_data(request.feed_ids)}


@app.post("/collect/hot-topics")
async def collect_hot_topics(request: CollectRequest):
    return {"success": True, "data": await collector.collect_hot_topics(request.keywords)}


@app.post("/publish/content")
async def publish_content(request: PublishRequest):
    result = await collector.mcp_client.call_tool(
        "publish_content",
        {"title": request.title, "content": request.content, "image_paths": request.image_paths or [], "tags": request.tags or []},
    )
    return {"success": "error" not in result, "data": result}


@app.post("/collect/start-scheduled")
async def start_scheduled(background_tasks: BackgroundTasks):
    started = collector.start(background_tasks)
    return {"status": "started" if started else "already_running", "interval": COLLECT_INTERVAL}


@app.post("/collect/stop")
async def stop_scheduled():
    collector.stop()
    return {"status": "stopped"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
