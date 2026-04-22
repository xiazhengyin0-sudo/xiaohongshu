"""
AI 分析引擎 - 基于 LangChain 集成多种国内 AI 模型
支持：智谱AI、通义千问、文心一言、DeepSeek、Moonshot
支持文字模型和图片模型分开选择
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Literal
import asyncio
import httpx
import json
import os
from datetime import datetime

# LangChain 核心组件
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

# LangChain 模型集成
from langchain_community.chat_models import ChatZhipuAI, ChatTongyi
from langchain_openai import ChatOpenAI

app = FastAPI(
    title="小红书 AI 分析引擎",
    description="基于 LangChain 的智能内容分析服务，支持文字和图片模型分开选择",
    version="3.0.0"
)

# ============= 文字模型配置 =============

TEXT_MODEL_PROVIDER = os.getenv("TEXT_MODEL_PROVIDER", "zhipu")
IMAGE_MODEL_PROVIDER = os.getenv("IMAGE_MODEL_PROVIDER", "zhipu")

TEXT_MODEL_CONFIGS = {
    "zhipu": {
        "name": "智谱AI (GLM-4)",
        "api_key_env": "ZHIPU_API_KEY",
        "model_env": "ZHIPU_MODEL",
        "default_model": "glm-4",
        "base_url": None
    },
    "qwen": {
        "name": "通义千问",
        "api_key_env": "QWEN_API_KEY",
        "model_env": "QWEN_MODEL",
        "default_model": "qwen-max",
        "base_url": None
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "default_model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1"
    },
    "moonshot": {
        "name": "Moonshot (Kimi)",
        "api_key_env": "MOONSHOT_API_KEY",
        "model_env": "MOONSHOT_MODEL",
        "default_model": "moonshot-v1-8k",
        "base_url": "https://api.moonshot.cn/v1"
    },
    "baidu": {
        "name": "文心一言",
        "api_key_env": "BAIDU_API_KEY",
        "model_env": "BAIDU_MODEL",
        "default_model": "ERNIE-Bot-4",
        "base_url": None
    }
}

# 图片模型配置
IMAGE_MODEL_CONFIGS = {
    "zhipu": {
        "name": "智谱AI (CogView)",
        "api_key_env": "ZHIPU_API_KEY",
        "model": "cogview-3",
        "type": "api"
    },
    "qwen": {
        "name": "通义万相",
        "api_key_env": "QWEN_API_KEY", 
        "model": "wanx-v1",
        "type": "api"
    },
    "baidu": {
        "name": "文心一格",
        "api_key_env": "BAIDU_API_KEY",
        "model": "ERNIE-ViLG",
        "type": "api"
    },
    "stable_diffusion": {
        "name": "Stable Diffusion",
        "api_key_env": "SD_API_KEY",
        "model": "sd-3",
        "base_url": os.getenv("SD_API_URL", "http://localhost:7860"),
        "type": "local"
    }
}

def get_llm(provider: str = None):
    """获取文字模型"""
    provider = provider or TEXT_MODEL_PROVIDER
    config = TEXT_MODEL_CONFIGS.get(provider)
    
    if not config:
        raise ValueError(f"不支持的 AI 提供商: {provider}")
    
    api_key = os.getenv(config["api_key_env"])
    model = os.getenv(config["model_env"], config["default_model"])
    
    if provider == "zhipu":
        return ChatZhipuAI(model=model, api_key=api_key, temperature=0.7)
    elif provider == "qwen":
        return ChatTongyi(model=model, dashscope_api_key=api_key, temperature=0.7)
    elif provider == "deepseek":
        return ChatOpenAI(model=model, api_key=api_key, base_url=config["base_url"], temperature=0.7)
    elif provider == "moonshot":
        return ChatOpenAI(model=model, api_key=api_key, base_url=config["base_url"], temperature=0.7)
    elif provider == "baidu":
        return ChatOpenAI(model=model, api_key=api_key, base_url="https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat", temperature=0.7)
    
    raise ValueError(f"无法初始化模型: {provider}")

async def generate_image(prompt: str, provider: str = None) -> str:
    """生成图片"""
    provider = provider or IMAGE_MODEL_PROVIDER
    config = IMAGE_MODEL_CONFIGS.get(provider)
    
    if not config:
        return None
    
    api_key = os.getenv(config["api_key_env"])
    
    try:
        if provider == "zhipu":
            # 智谱AI CogView
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://open.bigmodel.cn/api/paas/v4/images/generations",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": "cogview-3",
                        "prompt": prompt,
                        "size": "1024x1024"
                    },
                    timeout=60
                )
                result = response.json()
                return result.get("data", [{}])[0].get("url")
        
        elif provider == "qwen":
            # 通义万相
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "wanx-v1",
                        "input": {"text": prompt},
                        "parameters": {"size": "1024*1024"}
                    },
                    timeout=60
                )
                result = response.json()
                return result.get("output", {}).get("results", [{}])[0].get("url")
        
        elif provider == "stable_diffusion":
            # 本地 Stable Diffusion
            base_url = config.get("base_url", "http://localhost:7860")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/sdapi/v1/txt2img",
                    json={
                        "prompt": prompt,
                        "steps": 20,
                        "width": 1024,
                        "height": 1024
                    },
                    timeout=120
                )
                result = response.json()
                # 返回base64图片
                return f"data:image/png;base64,{result.get('images', [''])[0]}"
    
    except Exception as e:
        print(f"图片生成失败: {e}")
        return None
    
    return None

# ============= 数据模型 =============

class ContentAnalyzeRequest(BaseModel):
    """内容分析请求"""
    content: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    analyze_type: Literal["style", "sentiment", "keywords", "suggestions", "full"] = "full"

class StyleAnalyzeRequest(BaseModel):
    """账号风格分析请求"""
    posts: List[Dict]
    account_name: str
    platform: str = "xiaohongshu"

class ContentGenerateRequest(BaseModel):
    """内容生成请求"""
    topic: str
    style_reference: Optional[Dict] = None
    hot_keywords: Optional[List[str]] = None
    content_type: Literal["single", "series"] = "single"
    series_count: int = 5

class ContentContinueRequest(BaseModel):
    """内容续写请求"""
    historical_posts: List[Dict]  # 历史文章列表
    continue_topic: str  # 续写主题
    continue_count: int = 3  # 续写数量
    style_reference: Optional[Dict] = None

class CommentReplyRequest(BaseModel):
    """评论回复请求"""
    comment: str
    post_title: str
    post_content: str
    sentiment: Optional[str] = None

class ImageGenerateRequest(BaseModel):
    """图片生成请求"""
    prompt: str
    style: Optional[str] = "小红书风格"
    count: int = 1

# ============= 核心功能 =============

async def analyze_content_style(posts: List[Dict]) -> Dict:
    """分析账号内容风格"""
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""你是一位专业的小红书内容分析师。请分析以下账号的历史内容，提取其风格特征。

分析维度：
1. 语言风格：用词特点、语气、表达习惯、句式结构
2. 内容偏好：主题偏好、话题类型、内容深度
3. 表现形式：标题写法、段落结构、emoji使用频率和方式
4. 互动特征：引导语、话题标签使用、用户互动方式
5. 发布规律：最佳发布时间段、内容更新频率

请以JSON格式返回分析结果，包含以上所有维度。"""),
        HumanMessage(content=f"以下是该账号最近发布的内容样本：\n\n{json.dumps(posts, ensure_ascii=False, indent=2)}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = await chain.ainvoke({})
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        return {
            "language_style": "轻松活泼",
            "content_preference": ["职场干货", "生活分享"],
            "expression_style": "短句为主，善用emoji",
            "emoji_usage": ["💡", "✨", "📝", "🎯"],
            "interaction_style": "引导点赞收藏",
            "title_patterns": ["数字+主题", "疑问句开头", "感叹句结尾"],
            "paragraph_style": "2-3行一段，段落间空行",
            "best_posting_hours": [9, 12, 18, 21],
            "content_tone": "积极正能量，实用为主"
        }

async def continue_content_from_history(
    historical_posts: List[Dict],
    continue_topic: str,
    continue_count: int = 3,
    style_reference: Dict = None
) -> Dict:
    """基于历史内容续写"""
    llm = get_llm()
    
    # 提取历史内容的主题脉络
    historical_themes = []
    for post in historical_posts[:10]:
        historical_themes.append({
            "title": post.get("title", ""),
            "tags": post.get("tags", []),
            "summary": post.get("content", "")[:100]
        })
    
    style_info = ""
    if style_reference:
        style_info = f"\n\n请严格遵循以下风格特征：\n{json.dumps(style_reference, ensure_ascii=False, indent=2)}"
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=f"""你是一位小红书内容创作者，需要根据账号历史内容风格，续写系列内容。

历史内容主题脉络：
{json.dumps(historical_themes, ensure_ascii=False, indent=2)}
{style_info}

续写要求：
1. 延续历史内容的语言风格和表达习惯
2. 在原有主题基础上延伸新的相关话题
3. 保持相同的内容结构和格式特点
4. 使用相似的emoji和排版风格
5. 标题风格要和历史内容保持一致
6. 正文不超过1000字，标题不超过20字
7. 每篇包含3-5个话题标签

请生成{continue_count}篇续写内容，返回JSON格式：
{{
    "series_title": "系列主题",
    "continuity_analysis": "分析如何延续历史内容",
    "posts": [
        {{
            "order": 1,
            "title": "标题",
            "content": "正文内容",
            "tags": ["标签1", "标签2"],
            "connection_to_history": "说明与历史内容的关联"
        }}
    ]
}}"""),
        HumanMessage(content=f"请围绕「{continue_topic}」主题，基于账号历史内容风格续写{continue_count}篇内容")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = await chain.ainvoke({})
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        # 返回模拟数据
        return {
            "series_title": f"{continue_topic}系列",
            "continuity_analysis": "延续历史内容的实用风格",
            "posts": [{
                "order": i + 1,
                "title": f"💡 {continue_topic}实用技巧第{i+1}弹",
                "content": f"关于{continue_topic}，这期分享...\n\n📌 要点一：...\n📌 要点二：...\n\n希望有帮助！\n\n#{continue_topic} #干货分享",
                "tags": [continue_topic, "干货分享", "实用技巧"],
                "connection_to_history": "延续历史内容的实用干货风格"
            } for i in range(continue_count)]
        }

async def generate_content(
    topic: str,
    style_reference: Dict = None,
    hot_keywords: List[str] = None,
    content_type: str = "single",
    series_count: int = 5
) -> Dict:
    """生成内容"""
    llm = get_llm()
    
    style_info = ""
    if style_reference:
        style_info = f"\n\n请参考以下风格特征：\n{json.dumps(style_reference, ensure_ascii=False, indent=2)}"
    
    keywords_info = ""
    if hot_keywords:
        keywords_info = f"\n\n融入以下热点关键词：{', '.join(hot_keywords)}"
    
    if content_type == "series":
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""你是一位小红书内容创作专家。请为主题创建系列内容。

要求：
1. 每篇有不同角度，形成系列感
2. 标题不超过20字，有吸引力
3. 正文不超过1000字，善用emoji
4. 每篇3-5个话题标签
{style_info}{keywords_info}

返回JSON格式：
{{
    "series_title": "系列总标题",
    "posts": [
        {{
            "order": 1,
            "title": "标题",
            "content": "正文",
            "tags": ["标签"],
            "angle": "创作角度"
        }}
    ]
}}"""),
            HumanMessage(content=f"主题: {topic}，生成{series_count}篇系列内容")
        ])
    else:
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=f"""你是一位小红书内容创作专家。请为主题创作内容。

要求：
1. 标题吸引人，不超过20字
2. 正文实用，不超过1000字
3. 善用emoji增强可读性
4. 3-5个话题标签
5. 引导用户互动
{style_info}{keywords_info}

返回JSON格式：
{{
    "title": "标题",
    "content": "正文",
    "tags": ["标签"],
    "media_suggestions": ["配图建议"]
}}"""),
            HumanMessage(content=f"主题: {topic}")
        ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = await chain.ainvoke({})
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        return {
            "title": f"💡 {topic}实用技巧分享",
            "content": f"关于{topic}，总结了几个超实用的方法...\n\n📌 要点一：...\n📌 要点二：...\n\n希望有帮助！\n\n#{topic} #干货分享",
            "tags": [topic, "干货分享", "实用技巧"],
            "media_suggestions": ["封面使用醒目标题", "配图展示关键步骤"]
        }

async def generate_comment_reply(
    comment: str,
    post_title: str,
    post_content: str,
    sentiment: str = None
) -> str:
    """生成评论回复"""
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""你是一位友好的内容创作者，回复粉丝评论。

回复要求：
1. 语气亲切自然
2. 问题要给出有用回答
3. 表扬要表示感谢
4. 控制在50字以内
5. 可适当使用emoji"""),
        HumanMessage(content=f"""原帖: {post_title}
评论: {comment}
情感: {sentiment or '中性'}

生成回复:""")
    ])
    
    chain = prompt | llm | StrOutputParser()
    
    try:
        result = await chain.ainvoke({})
        return result.strip()
    except:
        return "感谢关注！有什么问题可以继续交流~"

# ============= API 路由 =============

@app.get("/")
async def root():
    return {
        "service": "小红书 AI 分析引擎",
        "version": "3.0.0",
        "text_model": TEXT_MODEL_CONFIGS[TEXT_MODEL_PROVIDER]["name"],
        "image_model": IMAGE_MODEL_CONFIGS[IMAGE_MODEL_PROVIDER]["name"],
        "status": "running"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "text_provider": TEXT_MODEL_PROVIDER,
        "image_provider": IMAGE_MODEL_PROVIDER
    }

@app.post("/analyze/style")
async def api_analyze_style(request: StyleAnalyzeRequest):
    """分析账号内容风格"""
    result = await analyze_content_style(request.posts)
    return {"success": True, "data": result}

@app.post("/analyze/content")
async def api_analyze_content(request: ContentAnalyzeRequest):
    """分析单个内容"""
    result = await analyze_single_content(
        content=request.content,
        title=request.title,
        analyze_type=request.analyze_type
    )
    return {"success": True, "data": result}

@app.post("/generate/content")
async def api_generate_content(request: ContentGenerateRequest):
    """生成内容"""
    result = await generate_content(
        topic=request.topic,
        style_reference=request.style_reference,
        hot_keywords=request.hot_keywords,
        content_type=request.content_type,
        series_count=request.series_count
    )
    return {"success": True, "data": result}

@app.post("/generate/continue")
async def api_continue_content(request: ContentContinueRequest):
    """基于历史内容续写"""
    result = await continue_content_from_history(
        historical_posts=request.historical_posts,
        continue_topic=request.continue_topic,
        continue_count=request.continue_count,
        style_reference=request.style_reference
    )
    return {"success": True, "data": result}

@app.post("/generate/image")
async def api_generate_image(request: ImageGenerateRequest):
    """生成图片"""
    full_prompt = f"{request.prompt}，{request.style}" if request.style else request.prompt
    result = await generate_image(full_prompt)
    return {"success": True, "image_url": result}

@app.post("/generate/reply")
async def api_generate_reply(request: CommentReplyRequest):
    """生成评论回复"""
    result = await generate_comment_reply(
        comment=request.comment,
        post_title=request.post_title,
        post_content=request.post_content,
        sentiment=request.sentiment
    )
    return {"success": True, "reply": result}

@app.get("/providers")
async def list_providers():
    """列出支持的模型提供商"""
    return {
        "text_models": {
            "current": TEXT_MODEL_PROVIDER,
            "providers": {
                k: {"name": v["name"], "model": os.getenv(v["model_env"], v["default_model"])}
                for k, v in TEXT_MODEL_CONFIGS.items()
            }
        },
        "image_models": {
            "current": IMAGE_MODEL_PROVIDER,
            "providers": {
                k: {"name": v["name"], "model": v["model"]}
                for k, v in IMAGE_MODEL_CONFIGS.items()
            }
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
