# -*- coding: utf-8 -*-
"""客服质检与工单分流助手 —— 同源 FastAPI 演示接口
在既有 main.py 的 app 上注册：
  GET  /                   公开演示网页（无登录）
  GET  /api/demo/health    健康检查
  POST /api/demo/single    单条分析（复用 graphs.graph.main_graph）
  POST /api/demo/batch     批量分析（复用 graphs.batch_graph.batch_main_graph）
密钥只在服务端 context/cozeloop 内使用，绝不返回前端；接口不落库、不保存用户原始对话。
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

import cozeloop
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.log.loop_trace import init_run_config

from demo_page import DEMO_PAGE_HTML
from graphs.batch_graph import batch_main_graph

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 900  # 与 main.py 一致：15 分钟

# —— 校验（复用已有图内校验，这里只做“能否进图”的轻量把关，给出清晰错误）——
def _coerce_record_json(body: Dict[str, Any]) -> str:
    """把 {ticket_id, messages} 或 {record_json} 转成 record_json 字符串。"""
    if isinstance(body.get("record_json"), str):
        s = body["record_json"].strip()
    else:
        tid = body.get("ticket_id")
        msgs = body.get("messages")
        if not isinstance(tid, str) or not tid.strip():
            raise HTTPException(status_code=400, detail="record 缺少非空的 ticket_id")
        if not isinstance(msgs, list) or len(msgs) < 1:
            raise HTTPException(status_code=400, detail="record.messages 必须是至少 1 条的数组")
        s = json.dumps({"ticket_id": tid.strip(), "messages": msgs}, ensure_ascii=False)
    try:
        obj = json.loads(s)
        if not isinstance(obj, dict) or not isinstance(obj.get("messages"), list):
            raise ValueError("messages 必须是数组")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"record_json 不是合法 JSON 对象: {e}")
    return s


def _coerce_records_json(body: Dict[str, Any]) -> str:
    if isinstance(body.get("records_json"), str):
        s = body["records_json"].strip()
    else:
        records = body.get("records")
        if not isinstance(records, list):
            raise HTTPException(status_code=400, detail="必须提供 records 数组或 records_json 字符串")
        s = json.dumps(records, ensure_ascii=False)
    try:
        arr = json.loads(s)
        if not isinstance(arr, list) or not (1 <= len(arr) <= 50):
            raise HTTPException(status_code=400, detail="records 必须是 1–50 条的数组")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"records_json 不是合法 JSON 数组: {e}")
    return s


async def _run_single(service, payload: Dict[str, Any], headers) -> Dict[str, Any]:
    ctx = new_context(method="demo_single", headers=headers)
    request_context.set(ctx)
    return await asyncio.wait_for(service.run(payload, ctx), timeout=TIMEOUT_SECONDS)


async def _run_batch(payload: Dict[str, Any], headers) -> Dict[str, Any]:
    ctx = new_context(method="demo_batch", headers=headers)
    request_context.set(ctx)
    run_config = init_run_config(batch_main_graph, ctx)
    run_config.setdefault("configurable", {})["thread_id"] = ctx.run_id
    try:
        return await asyncio.wait_for(
            batch_main_graph.ainvoke(payload, config=run_config, context=ctx),
            timeout=TIMEOUT_SECONDS,
        )
    finally:
        cozeloop.flush()


def register_demo_routes(app, service) -> None:
    @app.get("/", response_class=HTMLResponse)
    async def demo_index():
        return HTMLResponse(DEMO_PAGE_HTML, media_type="text/html; charset=utf-8")

    @app.get("/api/demo/health")
    async def demo_health():
        return {"status": "ok", "service": "customer_qa_demo"}

    @app.post("/api/demo/single")
    async def demo_single(request: Request) -> Dict[str, Any]:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="请求体必须是 JSON")
        record_json = _coerce_record_json(body)
        try:
            result = await _run_single(service, {"record_json": record_json}, request.headers)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="分析超时，请稍后重试")
        except Exception as e:
            logger.error(f"demo/single failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="服务端分析失败，请稍后重试")
        # 只返回结果字段，不返回任何密钥/上下文
        out: Dict[str, Any] = {"result_json": {}, "report": "", "needs_review": False}
        out["result_json"] = _safe_json(result.get("result_json"))
        out["report"] = result.get("report") or ""
        out["needs_review"] = bool(result.get("needs_review"))
        return out

    @app.post("/api/demo/batch")
    async def demo_batch(request: Request) -> Dict[str, Any]:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="请求体必须是 JSON")
        records_json = _coerce_records_json(body)
        try:
            result = await _run_batch({"records_json": records_json}, request.headers)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="批量分析超时，请稍后重试")
        except Exception as e:
            logger.error(f"demo/batch failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="服务端批量分析失败，请稍后重试")
        return {
            "summary_json": _safe_json(result.get("summary_json")),
            "report": result.get("report") or "",
        }


def _safe_json(value: Any) -> Any:
    if isinstance(value, (dict, list, int, float, bool)) or value is None:
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {"_raw": value}
    return {"_raw": str(value)}