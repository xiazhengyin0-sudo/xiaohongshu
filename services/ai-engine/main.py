"""
AI 分析引擎 - 基于 LangChain 集成多种国内 AI 模型。

服务在未配置 API Key 或模型调用失败时会返回可用的兜底结果，便于本地联调；生产环境请在
config/.env 中配置真实 Key。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.chat_models import ChatTongyi, ChatZhipuAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

app = FastAPI(
    title="小红书 AI 分析引擎",
    description="基于 LangChain 的智能内容分析服务，支持文字和图片模型分开选择",
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEXT_MODEL_PROVIDER = os.getenv("TEXT_MODEL_PROVIDER", os.getenv("AI_PROVIDER", "zhipu"))
IMAGE_MODEL_PROVIDER = os.getenv("IMAGE_MODEL_PROVIDER", "zhipu")

TEXT_MODEL_CONFIGS = {
    "zhipu": {
        "name": "智谱AI (GLM-4)",
        "api_key_env": "ZHIPU_API_KEY",
        "model_env": "ZHIPU_MODEL",
        "default_model": "glm-4",
        "base_url": None,
    },
    "qwen": {
        "name": "通义千问",
        "api_key_env": "QWEN_API_KEY",
        "model_env": "QWEN_MODEL",
        "default_model": "qwen-max",
        "base_url": None,
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
    },
    "moonshot": {
        "name": "Moonshot (Kimi)",
        "api_key_env": "MOONSHOT_API_KEY",
        "model_env": "MOONSHOT_MODEL",
        "default_model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1",
    },
}

IMAGE_MODEL_CONFIGS = {
    "zhipu": {"name": "智谱AI (CogView)", "api_key_env": "ZHIPU_API_KEY", "model": "cogview-3", "type": "api"},
    "qwen": {"name": "通义万相", "api_key_env": "QWEN_API_KEY", "model": "wanx-v1", "type": "api"},
    "stable_diffusion": {
        "name": "Stable Diffusion",
        "api_key_env": "SD_API_KEY",
        "model": "sd-3",
        "base_url": os.getenv("SD_API_URL", "http://localhost:7860"),
        "type": "local",
    },
}

PLACEHOLDER_VALUES = {"", "your_zhipu_api_key", "your_qwen_api_key", "your_deepseek_api_key", "your_moonshot_api_key"}


def configured_api_key(config: Dict[str, Any]) -> Optional[str]:
    api_key = os.getenv(config["api_key_env"], "").strip()
    return None if api_key in PLACEHOLDER_VALUES else api_key


def get_text_provider() -> str:
    return TEXT_MODEL_PROVIDER if TEXT_MODEL_PROVIDER in TEXT_MODEL_CONFIGS else "zhipu"


def get_image_provider() -> str:
    return IMAGE_MODEL_PROVIDER if IMAGE_MODEL_PROVIDER in IMAGE_MODEL_CONFIGS else "zhipu"


def get_llm(provider: Optional[str] = None):
    """获取文字模型；未配置 Key 时抛出可读错误，由调用方走兜底逻辑。"""
    provider = provider or get_text_provider()
    config = TEXT_MODEL_CONFIGS.get(provider)
    if not config:
        raise ValueError(f"不支持的 AI 提供商: {provider}")

    api_key = configured_api_key(config)
    if not api_key:
        raise ValueError(f"未配置 {config['name']} API Key，请设置 {config['api_key_env']}")

    model = os.getenv(config["model_env"], config["default_model"])
    if provider == "zhipu":
        return ChatZhipuAI(model=model, api_key=api_key, temperature=0.7)
    if provider == "qwen":
        return ChatTongyi(model=model, dashscope_api_key=api_key, temperature=0.7)
    return ChatOpenAI(model=model, api_key=api_key, base_url=config["base_url"], temperature=0.7)


def parse_json_response(raw: Any) -> Dict[str, Any]:
    """兼容模型输出 JSON、```json 代码块或前后带解释文本的情况。"""
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group(1))
            return parsed if isinstance(parsed, dict) else {"items": parsed}
        raise


def fallback_style(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    tags = []
    for post in posts:
        tags.extend(post.get("tags") or [])
    top_tags = list(dict.fromkeys(tags))[:5] or ["职场干货", "生活分享"]
    return {
        "language_style": "轻松、实用、口语化",
        "content_preference": top_tags,
        "expression_style": "短段落 + 列表化要点，适合移动端阅读",
        "emoji_usage": ["💡", "✨", "📝", "🎯"],
        "interaction_style": "结尾引导收藏、评论和提问",
        "title_patterns": ["数字清单型", "痛点提问型", "结果承诺型"],
        "paragraph_style": "2-3行一段，重点前置",
        "best_posting_hours": [9, 12, 18, 21],
        "content_tone": "积极正向，强调可执行方法",
        "note": "当前为本地兜底分析；配置真实 API Key 后可获得模型分析。",
    }


def fallback_single(topic: str, hot_keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    tags = [topic, "干货分享", "实用技巧"] + (hot_keywords or [])[:2]
    return {
        "title": f"💡 {topic}实用技巧",
        "content": f"关于{topic}，先别急着照搬别人的方法。\n\n📌 1. 先明确目标\n把你最想解决的问题写下来，避免内容发散。\n\n📌 2. 拆成可执行步骤\n每天完成一个小动作，比一次性做很多更稳定。\n\n📌 3. 定期复盘效果\n记录数据和反馈，保留有效动作，及时调整无效尝试。\n\n如果你也在关注{topic}，可以先收藏起来慢慢实践～",
        "tags": list(dict.fromkeys(tags))[:5],
        "media_suggestions": ["封面突出主题关键词", "正文配步骤清单图", "使用统一色系增强系列感"],
        "note": "当前为本地兜底生成；配置真实 API Key 后可获得模型生成。",
    }


def fallback_series(topic: str, count: int, hot_keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    posts = []
    angles = ["入门认知", "常见误区", "实操步骤", "工具清单", "复盘优化", "案例拆解", "进阶方法"]
    for i in range(count):
        post = fallback_single(f"{topic}·{angles[i % len(angles)]}", hot_keywords)
        post.update({"order": i + 1, "angle": angles[i % len(angles)]})
        posts.append(post)
    return {"series_title": f"{topic}系统提升系列", "posts": posts}


class ContentAnalyzeRequest(BaseModel):
    content: str = Field(..., min_length=1)
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    analyze_type: Literal["style", "sentiment", "keywords", "suggestions", "full"] = "full"


class StyleAnalyzeRequest(BaseModel):
    posts: List[Dict[str, Any]] = Field(..., min_length=1)
    account_name: str = ""
    platform: str = "xiaohongshu"


class ContentGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=80)
    style_reference: Optional[Dict[str, Any]] = None
    hot_keywords: Optional[List[str]] = None
    content_type: Literal["single", "series"] = "single"
    series_count: int = Field(5, ge=1, le=10)


class ContentContinueRequest(BaseModel):
    historical_posts: List[Dict[str, Any]] = Field(..., min_length=1)
    continue_topic: str = Field(..., min_length=1, max_length=80)
    continue_count: int = Field(3, ge=1, le=10)
    style_reference: Optional[Dict[str, Any]] = None


class CommentReplyRequest(BaseModel):
    comment: str = Field(..., min_length=1)
    post_title: str = ""
    post_content: str = ""
    sentiment: Optional[str] = None


class ImageGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    style: Optional[str] = "小红书风格"
    count: int = Field(1, ge=1, le=4)


async def analyze_content_style(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""你是一位专业的小红书内容分析师。请分析账号历史内容并返回严格 JSON。
字段包含：language_style, content_preference, expression_style, emoji_usage, interaction_style,
title_patterns, paragraph_style, best_posting_hours, content_tone。"""),
        HumanMessage(content=f"历史内容样本：\n{json.dumps(posts[:20], ensure_ascii=False, indent=2)}"),
    ])
    try:
        result = await (prompt | get_llm() | StrOutputParser()).ainvoke({})
        return parse_json_response(result)
    except Exception as exc:
        data = fallback_style(posts)
        data["fallback_reason"] = str(exc)
        return data


async def analyze_single_content(content: str, title: Optional[str] = None, analyze_type: str = "full") -> Dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="请以严格 JSON 分析小红书内容，字段包含 style, sentiment, keywords, suggestions, risk_tips。"),
        HumanMessage(content=f"分析类型：{analyze_type}\n标题：{title or ''}\n正文：{content}"),
    ])
    try:
        result = await (prompt | get_llm() | StrOutputParser()).ainvoke({})
        return parse_json_response(result)
    except Exception as exc:
        keywords = list(dict.fromkeys(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", f"{title or ''} {content}")))[:8]
        return {
            "style": "实用分享型",
            "sentiment": "中性偏积极",
            "keywords": keywords,
            "suggestions": ["标题加入明确收益点", "正文增加可执行步骤", "结尾加入互动问题"],
            "risk_tips": ["发布前确认内容真实合规", "避免夸大承诺或侵权素材"],
            "fallback_reason": str(exc),
        }


async def continue_content_from_history(historical_posts: List[Dict[str, Any]], continue_topic: str, continue_count: int = 3, style_reference: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    historical_themes = [{"title": p.get("title", ""), "tags": p.get("tags", []), "summary": p.get("content", "")[:160]} for p in historical_posts[:10]]
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=f"""你是一位小红书内容创作者，需要根据账号历史内容风格续写系列内容。返回严格 JSON：
{{"series_title":"系列主题","continuity_analysis":"续写分析","posts":[{{"order":1,"title":"标题","content":"正文","tags":["标签"],"connection_to_history":"关联说明"}}]}}
历史内容：{json.dumps(historical_themes, ensure_ascii=False)}
风格参考：{json.dumps(style_reference or {}, ensure_ascii=False)}"""),
        HumanMessage(content=f"请围绕「{continue_topic}」续写 {continue_count} 篇。"),
    ])
    try:
        result = await (prompt | get_llm() | StrOutputParser()).ainvoke({})
        return parse_json_response(result)
    except Exception as exc:
        data = fallback_series(continue_topic, continue_count)
        data["continuity_analysis"] = "延续历史内容的实用结构、短段落和清单化表达。"
        data["fallback_reason"] = str(exc)
        for post in data["posts"]:
            post["connection_to_history"] = "延续了历史内容的问题拆解和行动建议风格。"
        return data


async def generate_content(topic: str, style_reference: Optional[Dict[str, Any]] = None, hot_keywords: Optional[List[str]] = None, content_type: str = "single", series_count: int = 5) -> Dict[str, Any]:
    schema = "系列 JSON" if content_type == "series" else "单篇 JSON"
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=f"""你是一位小红书内容创作专家。请返回严格 JSON（不要 Markdown）。
要求：标题不超过20字，正文不超过1000字，3-5个标签，口语化、有行动建议。
输出类型：{schema}
风格参考：{json.dumps(style_reference or {}, ensure_ascii=False)}
热点关键词：{', '.join(hot_keywords or [])}"""),
        HumanMessage(content=f"主题：{topic}；生成类型：{content_type}；数量：{series_count}"),
    ])
    try:
        result = await (prompt | get_llm() | StrOutputParser()).ainvoke({})
        return parse_json_response(result)
    except Exception as exc:
        data = fallback_series(topic, series_count, hot_keywords) if content_type == "series" else fallback_single(topic, hot_keywords)
        data["fallback_reason"] = str(exc)
        return data


async def generate_comment_reply(comment: str, post_title: str, post_content: str, sentiment: Optional[str] = None) -> str:
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="你是一位友好的内容创作者，回复粉丝评论。回复 50 字以内，亲切、有帮助，可适当使用 emoji。"),
        HumanMessage(content=f"原帖：{post_title}\n评论：{comment}\n情感：{sentiment or '中性'}\n生成回复："),
    ])
    try:
        return (await (prompt | get_llm() | StrOutputParser()).ainvoke({})).strip()
    except Exception:
        return "谢谢你的留言～我会继续整理更实用的内容，也欢迎说说你最想看的方向 😊"


async def generate_image(prompt: str, provider: Optional[str] = None) -> Optional[str]:
    provider = provider or get_image_provider()
    config = IMAGE_MODEL_CONFIGS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"不支持的图片模型: {provider}")

    api_key = configured_api_key(config)
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if provider == "zhipu":
                if not api_key:
                    raise ValueError("未配置 ZHIPU_API_KEY")
                response = await client.post(
                    "https://open.bigmodel.cn/api/paas/v4/images/generations",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": config["model"], "prompt": prompt, "size": "1024x1024"},
                )
                response.raise_for_status()
                return response.json().get("data", [{}])[0].get("url")
            if provider == "qwen":
                if not api_key:
                    raise ValueError("未配置 QWEN_API_KEY")
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": config["model"], "input": {"text": prompt}, "parameters": {"size": "1024*1024"}},
                )
                response.raise_for_status()
                return response.json().get("output", {}).get("results", [{}])[0].get("url")
            if provider == "stable_diffusion":
                response = await client.post(
                    f"{config.get('base_url')}/sdapi/v1/txt2img",
                    json={"prompt": prompt, "steps": 20, "width": 1024, "height": 1024},
                )
                response.raise_for_status()
                return f"data:image/png;base64,{response.json().get('images', [''])[0]}"
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"图片生成失败: {exc}") from exc
    return None


@app.get("/")
async def root():
    text_provider = get_text_provider()
    image_provider = get_image_provider()
    return {
        "service": "小红书 AI 分析引擎",
        "version": "3.1.0",
        "text_model": TEXT_MODEL_CONFIGS[text_provider]["name"],
        "image_model": IMAGE_MODEL_CONFIGS[image_provider]["name"],
        "configured": bool(configured_api_key(TEXT_MODEL_CONFIGS[text_provider])),
        "status": "running",
    }


@app.get("/health")
async def health():
    text_provider = get_text_provider()
    return {
        "status": "healthy",
        "text_provider": text_provider,
        "image_provider": get_image_provider(),
        "text_model_configured": bool(configured_api_key(TEXT_MODEL_CONFIGS[text_provider])),
    }


@app.post("/analyze/style")
async def api_analyze_style(request: StyleAnalyzeRequest):
    return {"success": True, "data": await analyze_content_style(request.posts)}


@app.post("/analyze/content")
async def api_analyze_content(request: ContentAnalyzeRequest):
    return {"success": True, "data": await analyze_single_content(request.content, request.title, request.analyze_type)}


@app.post("/generate/content")
async def api_generate_content(request: ContentGenerateRequest):
    return {"success": True, "data": await generate_content(request.topic, request.style_reference, request.hot_keywords, request.content_type, request.series_count)}


@app.post("/generate/continue")
async def api_continue_content(request: ContentContinueRequest):
    return {"success": True, "data": await continue_content_from_history(request.historical_posts, request.continue_topic, request.continue_count, request.style_reference)}


@app.post("/generate/image")
async def api_generate_image(request: ImageGenerateRequest):
    full_prompt = f"{request.prompt}，{request.style}" if request.style else request.prompt
    return {"success": True, "image_url": await generate_image(full_prompt)}


@app.post("/generate/reply")
async def api_generate_reply(request: CommentReplyRequest):
    return {"success": True, "reply": await generate_comment_reply(request.comment, request.post_title, request.post_content, request.sentiment)}


@app.get("/providers")
async def list_providers():
    return {
        "text_models": {
            "current": get_text_provider(),
            "providers": {
                k: {"name": v["name"], "model": os.getenv(v["model_env"], v["default_model"]), "configured": bool(configured_api_key(v))}
                for k, v in TEXT_MODEL_CONFIGS.items()
            },
        },
        "image_models": {
            "current": get_image_provider(),
            "providers": {k: {"name": v["name"], "model": v["model"], "type": v["type"]} for k, v in IMAGE_MODEL_CONFIGS.items()},
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
