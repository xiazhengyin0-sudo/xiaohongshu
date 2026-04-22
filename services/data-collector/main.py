"""
数据采集服务 - 通过 MCP 协议采集小红书数据
"""
import asyncio
import httpx
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
import schedule
import threading
import time

# 数据存储
DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

XHS_MCP_URL = os.getenv("XHS_MCP_URL", "http://localhost:18060/mcp")
COLLECT_INTERVAL = int(os.getenv("COLLECT_INTERVAL", 3600))

class XHSMCPClient:
    """小红书 MCP 客户端"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.request_id = 0
    
    async def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """调用 MCP 工具"""
        self.request_id += 1
        
        # MCP 协议请求格式
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            },
            "id": self.request_id
        }
        
        try:
            response = await self.client.post(
                self.base_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            result = response.json()
            
            if "error" in result:
                print(f"❌ MCP 错误: {result['error']}")
                return {"error": result["error"]}
            
            return result.get("result", {})
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return {"error": str(e)}
    
    async def check_login(self) -> bool:
        """检查登录状态"""
        result = await self.call_tool("check_login_status")
        return result.get("logged_in", False)
    
    async def get_login_qrcode(self) -> dict:
        """获取登录二维码"""
        return await self.call_tool("get_login_qrcode")
    
    async def get_user_profile(self, user_id: str, xsec_token: str = None) -> dict:
        """获取用户主页信息"""
        return await self.call_tool("user_profile", {
            "user_id": user_id,
            "xsec_token": xsec_token
        })
    
    async def get_feed_detail(self, feed_id: str, xsec_token: str = None) -> dict:
        """获取帖子详情"""
        return await self.call_tool("get_feed_detail", {
            "feed_id": feed_id,
            "xsec_token": xsec_token
        })
    
    async def search_feeds(self, keyword: str, **filters) -> dict:
        """搜索内容"""
        return await self.call_tool("search_feeds", {
            "keyword": keyword,
            **filters
        })
    
    async def list_feeds(self) -> dict:
        """获取首页推荐"""
        return await self.call_tool("list_feeds")

class DataCollector:
    """数据采集器"""
    
    def __init__(self):
        self.mcp_client = XHSMCPClient(XHS_MCP_URL)
        self.is_running = False
    
    async def collect_account_data(self, user_id: str = None) -> Dict:
        """采集账号数据"""
        print(f"📊 开始采集账号数据...")
        
        # 检查登录状态
        logged_in = await self.mcp_client.check_login()
        if not logged_in:
            print("⚠️ 未登录小红书，需要先登录")
            qrcode = await self.mcp_client.get_login_qrcode()
            return {
                "status": "need_login",
                "qrcode": qrcode.get("qr_code_base64"),
                "message": "请扫描二维码登录"
            }
        
        # 获取用户数据（如果指定了用户ID）
        if user_id:
            profile = await self.mcp_client.get_user_profile(user_id)
            return {
                "status": "success",
                "data": {
                    "profile": profile,
                    "collected_at": datetime.now().isoformat()
                }
            }
        
        return {"status": "success", "message": "已登录，准备采集"}
    
    async def collect_feed_data(self, feed_ids: List[str]) -> List[Dict]:
        """采集指定帖子的数据"""
        results = []
        
        for feed_id in feed_ids:
            try:
                detail = await self.mcp_client.get_feed_detail(feed_id)
                results.append({
                    "feed_id": feed_id,
                    "data": detail,
                    "collected_at": datetime.now().isoformat()
                })
                await asyncio.sleep(1)  # 避免请求过快
            except Exception as e:
                results.append({
                    "feed_id": feed_id,
                    "error": str(e)
                })
        
        return results
    
    async def collect_hot_topics(self, keywords: List[str] = None) -> Dict:
        """采集热点话题数据"""
        print(f"🔥 采集热点话题...")
        
        # 默认搜索关键词
        search_keywords = keywords or [
            "职场干货", "穿搭分享", "美食探店", 
            "护肤心得", "居家好物", "旅行攻略"
        ]
        
        results = {}
        for keyword in search_keywords:
            try:
                search_result = await self.mcp_client.search_feeds(keyword)
                results[keyword] = search_result
                await asyncio.sleep(2)
            except Exception as e:
                results[keyword] = {"error": str(e)}
        
        # 保存数据
        self._save_data("hot_topics.json", results)
        
        return results
    
    async def collect_trending_feeds(self) -> Dict:
        """采集首页推荐内容"""
        print(f"📱 采集首页推荐...")
        
        try:
            feeds = await self.mcp_client.list_feeds()
            self._save_data("trending_feeds.json", feeds)
            return feeds
        except Exception as e:
            return {"error": str(e)}
    
    def _save_data(self, filename: str, data: dict):
        """保存数据到文件"""
        filepath = DATA_DIR / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "data": data,
                "updated_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        print(f"✅ 数据已保存: {filepath}")
    
    async def run_scheduled_collection(self):
        """定时采集任务"""
        print(f"⏰ 启动定时采集，间隔: {COLLECT_INTERVAL}秒")
        self.is_running = True
        
        while self.is_running:
            try:
                # 采集热点
                await self.collect_hot_topics()
                
                # 采集首页推荐
                await self.collect_trending_feeds()
                
                print(f"✅ 本轮采集完成，下次采集: {COLLECT_INTERVAL}秒后")
            except Exception as e:
                print(f"❌ 采集出错: {e}")
            
            await asyncio.sleep(COLLECT_INTERVAL)
    
    def stop(self):
        """停止采集"""
        self.is_running = False

# FastAPI 服务
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel

app = FastAPI(
    title="小红书数据采集服务",
    version="1.0.0"
)

collector = DataCollector()

class CollectRequest(BaseModel):
    feed_ids: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    user_id: Optional[str] = None

@app.get("/")
async def root():
    return {"service": "小红书数据采集服务", "status": "running"}

@app.get("/health")
async def health():
    logged_in = await collector.mcp_client.check_login()
    return {"status": "healthy", "xhs_logged_in": logged_in}

@app.post("/collect/account")
async def collect_account(request: CollectRequest):
    """采集账号数据"""
    result = await collector.collect_account_data(request.user_id)
    return result

@app.post("/collect/feeds")
async def collect_feeds(request: CollectRequest):
    """采集帖子数据"""
    if not request.feed_ids:
        return {"error": "请提供 feed_ids"}
    result = await collector.collect_feed_data(request.feed_ids)
    return {"status": "success", "data": result}

@app.post("/collect/hot-topics")
async def collect_hot_topics(request: CollectRequest):
    """采集热点话题"""
    result = await collector.collect_hot_topics(request.keywords)
    return {"status": "success", "data": result}

@app.post("/collect/start-scheduled")
async def start_scheduled(background_tasks: BackgroundTasks):
    """启动定时采集"""
    background_tasks.add_task(collector.run_scheduled_collection)
    return {"status": "started", "interval": COLLECT_INTERVAL}

@app.post("/collect/stop")
async def stop_scheduled():
    """停止定时采集"""
    collector.stop()
    return {"status": "stopped"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
