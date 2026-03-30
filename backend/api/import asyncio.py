import asyncio
import time
from typing import Optional, Iterator

import openai  # 或其他模型 SDK

API_TIMEOUT = 120  # 单次请求超时（秒）
RETRY_MAX = 3
RETRY_BACKOFF = 2.0

def _retry_sleep(attempt: int):
    time.sleep(RETRY_BACKOFF ** attempt)

async def call_model_async(prompt: str, max_tokens: int = 1024, temperature: float = 0.2, timeout: int = API_TIMEOUT) -> str:
    last_err = None
    for attempt in range(RETRY_MAX):
        try:
            # openai sdk 示例
            resp = await asyncio.wait_for(
                openai.ChatCompletion.acreate(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=1.0,
                ),
                timeout=timeout,
            )
            return resp.choices[0].message["content"].strip()
        except (asyncio.TimeoutError, openai.error.Timeout) as exc:
            last_err = exc
            _retry_sleep(attempt)
        except openai.error.RateLimitError as exc:
            last_err = exc
            _retry_sleep(attempt)
        except Exception as exc:
            last_err = exc
            break
    raise RuntimeError(f"LLM 调用失败: {last_err}")

async def stream_model_async(prompt: str, max_tokens: int = 2048, temperature: float = 0.2, timeout: int = API_TIMEOUT) -> Iterator[str]:
    # 高并发时可做增量输出，避免超时等待
    # 仅支持SDK stream版本
    async with openai.ChatCompletion.acreate(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    ) as stream:
        start = time.time()
        async for chunk in stream:
            if time.time() - start > timeout:
                raise asyncio.TimeoutError("LLM流式超时")
            if chunk.choices[0].delta.get("content"):
                yield chunk.choices[0].delta["content"]

from fastapi import APIRouter, BackgroundTasks, HTTPException

router = APIRouter()

async def summarize_dialogue(messages, knowledge) -> str:
    prompt = "...断点设计为小段身体控制..."
    # 将对话与知识库拆成小块，多次调用
    # 最终拼接成大纲
    segments = []
    for chunk in chunk_text("\n".join([m["content"] for m in messages]), size=1200):
        txt = await call_model_async(f"请归纳这一段要点：\n{chunk}", max_tokens=400)
        segments.append(txt)
    outline = await call_model_async(f"根据下面内容输出PPT要点：\n{join_segments(segments)}", max_tokens=600)
    return outline

def chunk_text(text: str, size: int):
    for i in range(0, len(text), size):
        yield text[i : i + size]

async def generate_ppt_task(task_id, payload):
    # ...状态逻辑...
    try:
        outline = await summarize_dialogue(payload.messages, payload.knowledge)
        # 逐页生成，单页请求控制在 max_tokens 范围
        pages = parse_outline(outline, payload.slide_count)
        slides = []
        for i, page in enumerate(pages, 1):
            text_prompt = f"第{i}页标题：{page['title']}\n要点：{';'.join(page['points'])}\n请输出 100-220 字的正文。"
            # 低频次，放到异步等待
            content = await call_model_async(text_prompt, max_tokens=300, timeout=90)
            slides.append({"title": page["title"], "content": content})
        # 生成pptx
        # ...
    except Exception as e:
        # 失败状态
        # ...