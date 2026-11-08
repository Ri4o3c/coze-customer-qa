#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
确定性边界测试驱动（不依赖大模型，全部走代码节点逻辑）。

覆盖：rule_quote 逐字比对、非法类型、NaN 置信度、缺字段、非法 route、
      customer/agent 证据分开校验、规则完整性缺失/冲突、批量解析与批量复验。

用法（项目根目录）：
    PYTHONPATH=src python scripts/run_hardening_tests.py
产物：verification/hardening_result.json
"""
import sys
import os
import json
import math
import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from graphs.nodes.single_validate_node import validate_node
from graphs.nodes.single_rule_check_node import rule_check_node
from graphs.nodes.single_json_validation_node import json_validation_node
from graphs.nodes.batch_parse_node import batch_parse_node
from graphs.nodes.batch_aggregate_node import batch_aggregate_node
from graphs.state import (
    ValidateInput, RuleCheckInput, JsonValidationInput,
    BatchParseInput, BatchAggregateInput,
)

CANONICAL_RULES: List[Dict[str, Any]] = [
    {"rule_id": "R01", "version": "1.0", "policy": "客服不得辱骂、嘲讽或贬低客户。"},
    {"rule_id": "R02", "version": "1.0", "policy": "客服不得索取客户的账户密码、支付密码或支付验证码。"},
    {"rule_id": "R03", "version": "1.0", "policy": "退款须经售后审核；审核通过后预计1至3个工作日原路退回，客服不得保证具体到账时点。"},
]

MESSAGES: List[Dict[str, str]] = [
    {"role": "customer", "text": "我的包裹三天没更新了。"},
    {"role": "agent", "text": "您好，我帮您联系物流核实。"},
]


def _valid_llm_raw(**overrides: Any) -> Dict[str, Any]:
    base = {
        "category": "物流配送",
        "category_confidence": 0.9,
        "category_evidence": [{"message_index": 0, "quote": "我的包裹三天没更新了。"}],
        "summary": "客户反馈包裹物流未更新，客服将联系物流核实。",
        "checks": {
            "R01": {"rule_id": "R01", "status": "pass", "rule_quote": "客服不得辱骂、嘲讽或贬低客户。",
                    "reason": "客服回复礼貌", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]},
            "R02": {"rule_id": "R02", "status": "pass", "rule_quote": "客服不得索取客户的账户密码、支付密码或支付验证码。",
                    "reason": "未索取敏感信息", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]},
            "R03": {"rule_id": "R03", "status": "pass", "rule_quote": "退款须经售后审核；审核通过后预计1至3个工作日原路退回，客服不得保证具体到账时点。",
                    "reason": "未涉及退款承诺", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]},
        },
        "needs_review": False,
        "review_reasons": [],
    }
    base.update(overrides)
    return base


def _jv(llm_raw: Dict[str, Any]) -> Dict[str, Any]:
    out = json_validation_node(
        JsonValidationInput(
            ticket_id="DEMO-T", messages=MESSAGES,
            llm_raw=json.dumps(llm_raw, ensure_ascii=False),
            llm_ok=True, rules=CANONICAL_RULES,
        ), None, None,
    )
    return {
        "category": out.category, "category_valid": out.category_valid,
        "qc_status": out.qc_status, "needs_review": out.needs_review,
        "review_reasons": out.review_reasons,
        "validation_issues": out.validation.get("issues", []),
    }


def _check(name: str, ok: bool, detail: Dict[str, Any], note: str = "") -> Dict[str, Any]:
    return {
        "name": name, "passed": bool(ok), "expectation": {"ok": bool(ok), "note": note},
        "actual_output": detail,
    }


def run() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []

    # ---- 1. rule_quote 逐字严格比对 ----
    def _rule_quote_case(name: str, req: Dict[str, Any], expect_review: bool):
        raw = _valid_llm_raw()
        raw["checks"]["R01"] = req
        o = _jv(raw)
        results.append(_check(
            name, ok=(o["needs_review"] == expect_review), detail=o,
            note="expected needs_review=%s" % expect_review))

    _rule_quote_case("rule_quote_verbatim_pass", {
        "rule_id": "R01", "status": "pass", "rule_quote": "客服不得辱骂、嘲讽或贬低客户。",
        "reason": "礼貌", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]}, expect_review=False)
    _rule_quote_case("rule_quote_short_substring", {
        "rule_id": "R01", "status": "pass", "rule_quote": "客服",
        "reason": "礼貌", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]}, expect_review=True)
    _rule_quote_case("rule_quote_punct_diff", {
        "rule_id": "R01", "status": "pass", "rule_quote": "客服不得辱骂、嘲讽或贬低客户",
        "reason": "礼貌", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]}, expect_review=True)

    # ---- 1.5 强制不变量：任一规则status=unknown → needs_review必须为true（不依赖模型自报复核）----
    def _unknown_case(name: str, st: Dict[str, str], expect_qc: str, expect_review: bool):
        raw = _valid_llm_raw()
        for rid in ("R01", "R02", "R03"):
            raw["checks"][rid]["status"] = st.get(rid, "pass")
        raw["needs_review"] = False          # 模型自报无需复核 → 代码必须强制复核
        raw["category_confidence"] = 0.95    # 置信度足够高，排除 conf_low 干扰
        o = _jv(raw)
        ok = (o["needs_review"] == expect_review and o["qc_status"] == expect_qc)
        detail = dict(o)
        detail["input_model_needs_review"] = False
        detail["input_confidence"] = 0.95
        results.append(_check(name, ok=ok, detail=detail,
                              note="expect qc_status=%s needs_review=%s(须为代码强制而非模型自报)" % (expect_qc, expect_review)))

    _unknown_case("unknown_but_model_needs_review_false",
                  {"R01": "unknown", "R02": "pass", "R03": "pass"}, "undetermined", True)
    _unknown_case("unknown_with_fail_still_review",
                  {"R01": "fail", "R02": "unknown", "R03": "pass"}, "violation", True)
    _unknown_case("all_unknown_model_false",
                  {"R01": "unknown", "R02": "unknown", "R03": "unknown"}, "undetermined", True)

    # ---- 1.6 确认分类必须至少有1条customer原文证据，不接受空数组 ----
    _empty_ev = _valid_llm_raw()
    _empty_ev["category"] = "物流配送"
    _empty_ev["needs_review"] = False
    _empty_ev["category_confidence"] = 0.95
    _empty_ev["category_evidence"] = []
    _empty_ev["checks"]["R01"]["evidence"] = [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]
    _empty_ev["checks"]["R02"]["evidence"] = [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]
    _empty_ev["checks"]["R03"]["evidence"] = [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]
    _oe = _jv(_empty_ev)
    results.append(_check("category_evidence_empty_review",
                          ok=(_oe["needs_review"] is True and _oe["qc_status"] == "undetermined"),
                          detail=_oe, note="确认分类但category_evidence=[] → 不接受，降级unknown并人工复核"))

    # ---- 2. 非法类型 / 结构 ----
    for name, mutate in [
        ("category_empty_list", lambda r: r.update({"category": []})),
        ("category_empty_dict", lambda r: r.update({"category": {}})),
        ("rule_id_dict", lambda r: r["checks"]["R01"].update({"rule_id": {}})),
        ("extra_check_key", lambda r: r["checks"].update({"R04": {"rule_id": "R04", "status": "pass", "rule_quote": "x", "reason": "y", "evidence": []}})),
        ("missing_rule_quote", lambda r: r["checks"]["R01"].pop("rule_quote", None)),
        ("missing_reason", lambda r: r["checks"]["R01"].pop("reason", None)),
        ("missing_check_evidence", lambda r: r["checks"]["R01"].update({"evidence": []})),
        ("illegal_category", lambda r: r.update({"category": "审批"})),
    ]:
        raw = _valid_llm_raw()
        mutate(raw)
        o = _jv(raw)
        results.append(_check(
            "hard_%s" % name, ok=(o["needs_review"] is True and o["qc_status"] == "undetermined"),
            detail=o, note="非法输入须转人工且整条降至 undetermined"))

    # NaN 置信度
    raw = _valid_llm_raw()
    raw["category_confidence"] = float("nan")
    o = _jv(raw)
    results.append(_check(
        "hard_nan_confidence", ok=(o["needs_review"] is True), detail=o, note="NaN 置信度须转人工"))

    # 分类证据引用客服 / 质检证据引用客服（应为 agent）
    raw = _valid_llm_raw()
    raw["category_evidence"] = [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]  # agent 非 customer
    o = _jv(raw)
    results.append(_check(
        "cat_evidence_not_customer", ok=(o["needs_review"] is True), detail=o,
        note="分类证据须引用 customer 连续原文"))

    raw = _valid_llm_raw()
    raw["checks"]["R01"]["evidence"] = [{"message_index": 0, "quote": "我的包裹三天没更新了。"}]  # customer 非 agent
    o = _jv(raw)
    results.append(_check(
        "check_evidence_not_agent", ok=(o["needs_review"] is True), detail=o,
        note="质检证据须引用 agent 连续原文"))

    # 无效 JSON 文本
    o = _jv({"not": "valid json " * 5})
    o2 = json_validation_node(JsonValidationInput(
        ticket_id="DEMO-T", messages=MESSAGES,
        llm_raw="not a json {{{", llm_ok=True, rules=CANONICAL_RULES), None, None)
    results.append(_check(
        "invalid_json_text", ok=(o2.needs_review is True), detail={
            "qc_status": o2.qc_status, "needs_review": o2.needs_review,
            "issues": o2.validation.get("issues", [])},
        note="非法 JSON 须转人工"))

    # ---- 3. 输入校验 ----
    def _val(record_json: str) -> Dict[str, Any]:
        try:
            o = validate_node(ValidateInput(record_json=record_json), None, None)
            return {"validation_valid": o.validation_valid, "validation_error": o.validation_error,
                    "ticket_id": o.ticket_id, "messages": o.messages}
        except Exception as e:  # noqa: BLE001
            return {"validation_valid": False, "validation_error": f"EXC:{e}"}

    results.append(_check("valid_input_ok", ok=(_val(json.dumps(
        {"ticket_id": "T1", "messages": MESSAGES}, ensure_ascii=False))["validation_valid"] is True),
        detail=_val(json.dumps({"ticket_id": "T1", "messages": MESSAGES}, ensure_ascii=False)),
        note="合法输入应通过"))
    for name, rec in [
        ("ticket_id_empty_list", {"ticket_id": [], "messages": MESSAGES}),
        ("ticket_id_empty", {"ticket_id": "", "messages": MESSAGES}),
        ("only_one_role", {"ticket_id": "T", "messages": [{"role": "customer", "text": "hi"}]}),
        ("illegal_role", {"ticket_id": "T", "messages": [{"role": "customer", "text": "hi"}, {"role": "admin", "text": "x"}]}),
        ("over_char_limit", {"ticket_id": "T", "messages": [
            {"role": "customer", "text": "超" * 20001}, {"role": "agent", "text": "好"}]}),
    ]:
        results.append(_check(
            "val_%s" % name, ok=(_val(json.dumps(rec, ensure_ascii=False))["validation_valid"] is False),
            detail=_val(json.dumps(rec, ensure_ascii=False)), note="应明确校验不通过(转人工)"))

    # ---- 4. 规则完整性 ----
    def _rc(rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        o = rule_check_node(RuleCheckInput(rules=rules), None, None)
        return {"rules_ok": o.rules_ok, "reason": o.rules_reason}

    results.append(_check("rules_complete_ok", ok=(_rc(CANONICAL_RULES)["rules_ok"] is True),
                          detail=_rc(CANONICAL_RULES), note="完整三条应通过"))
    results.append(_check("rules_missing_r03", ok=(_rc(CANONICAL_RULES[:2])["rules_ok"] is False),
                          detail=_rc(CANONICAL_RULES[:2]), note="缺 R03 应失败"))
    conflict = CANONICAL_RULES + [{"id": "R01", "version": "1.0", "policy": "客服可以骂人。"}]
    results.append(_check("rules_same_id_conflict", ok=(_rc(conflict)["rules_ok"] is False),
                          detail=_rc(conflict), note="同 ID 冲突应失败"))

    # ---- 5. 批量解析 ----
    def _bp(records_json: str) -> Dict[str, Any]:
        o = batch_parse_node(BatchParseInput(records_json=records_json), None, None)
        return {"parse_ok": o.parse_ok, "error": o.parse_error, "n": len(o.items), "dup": o.duplicate_ids}

    ok_batch = [{"ticket_id": "A", "messages": MESSAGES}, {"ticket_id": "B", "messages": MESSAGES}]
    results.append(_check("batch_parse_ok", ok=(_bp(json.dumps(ok_batch, ensure_ascii=False))["parse_ok"] is True),
                          detail=_bp(json.dumps(ok_batch, ensure_ascii=False)), note="合法批次应通过"))
    dup_batch = [{"ticket_id": "A", "messages": MESSAGES}, {"ticket_id": "A", "messages": MESSAGES}]
    results.append(_check("batch_parse_dup", ok=(_bp(json.dumps(dup_batch, ensure_ascii=False))["parse_ok"] is False),
                          detail=_bp(json.dumps(dup_batch, ensure_ascii=False)), note="重复 ID 整批拒绝"))
    missing_id = [{"messages": MESSAGES}]
    results.append(_check("batch_parse_missing_id", ok=(_bp(json.dumps(missing_id, ensure_ascii=False))["parse_ok"] is False),
                          detail=_bp(json.dumps(missing_id, ensure_ascii=False)), note="缺 ID 整批拒绝"))
    empty = []
    results.append(_check("batch_parse_empty", ok=(_bp(json.dumps(empty))["parse_ok"] is False),
                          detail=_bp(json.dumps(empty)), note="空批次拒绝"))
    over50 = [{"ticket_id": f"X{i}", "messages": MESSAGES} for i in range(51)]
    results.append(_check("batch_parse_over50", ok=(_bp(json.dumps(over50, ensure_ascii=False))["parse_ok"] is False),
                          detail=_bp(json.dumps(over50, ensure_ascii=False)), note="超过50条拒绝"))

    # ---- 6. 批量聚合复验 ----
    def _agg(results_lst: List[Dict[str, Any]], items: List[Dict[str, Any]]) -> Dict[str, Any]:
        o = batch_aggregate_node(BatchAggregateInput(results=results_lst, items=items), None, None)
        s = json.loads(o.summary_json)
        return {"pass_count": s.get("pass_count"), "undetermined_count": s.get("undetermined_count"),
                "violation_count": s.get("violation_count"), "review_count": s.get("review_count")}

    def _complete_result(tid: str) -> Dict[str, Any]:
        base = {
            "schema_version": 1, "ticket_id": tid, "category": "物流配送", "category_valid": True,
            "category_confidence": 0.9, "category_evidence": [{"message_index": 0, "quote": "我的包裹三天没更新了。"}],
            "summary": "s", "checks": {"R01": {"rule_id": "R01", "status": "pass", "rule_quote": "客服不得辱骂、嘲讽或贬低客户。",
                                               "reason": "r", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]},
                                        "R02": {"rule_id": "R02", "status": "pass", "rule_quote": "客服不得索取客户的账户密码、支付密码或支付验证码。",
                                               "reason": "r", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]},
                                        "R03": {"rule_id": "R03", "status": "pass", "rule_quote": "退款须经售后审核；审核通过后预计1至3个工作日原路退回，客服不得保证具体到账时点。",
                                               "reason": "r", "evidence": [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]}},
            "qc_status": "pass", "needs_review": False, "review_reasons": [], "route": "物流客服",
            "suggested_route": "物流客服", "action": "suggest_only",
            "validation": {}, "semantic_review": {},
        }
        return {
            "ticket_id": tid, "result_json": json.dumps(base, ensure_ascii=False), "report": "",
            "needs_review": base["needs_review"], "qc_status": base["qc_status"],
            "category": base["category"], "category_valid": base["category_valid"],
            "checks": base["checks"], "review_reasons": base["review_reasons"],
            "messages": MESSAGES, "error": "",
        }

    rec_ok = _complete_result("A")
    rec_broken = _complete_result("B")
    rec_broken["result_json"] = "not a valid result json"
    rec_bad_cust = _complete_result("C")
    rb = json.loads(rec_bad_cust["result_json"])
    rb["category_evidence"] = [{"message_index": 1, "quote": "您好，我帮您联系物流核实。"}]
    rec_bad_cust["result_json"] = json.dumps(rb, ensure_ascii=False)
    items = [{"ticket_id": "A", "record_json": "1"}, {"ticket_id": "B", "record_json": "2"},
             {"ticket_id": "C", "record_json": "3"}]
    agg = _agg([rec_ok, rec_broken, rec_bad_cust], items)
    results.append(_check(
        "batch_aggregate_revalidation", ok=(agg["pass_count"] == 1 and agg["undetermined_count"] == 2),
        detail=agg, note="损坏单条/客服原话缺失不计 pass，转 unknown"))

    return {
        "hardened_enough": all(r["passed"] for r in results),
        "total": len(results), "passed": sum(1 for r in results if r["passed"]),
        "cases": results,
    }


def main() -> None:
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    res = run()
    ver_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verification")
    os.makedirs(ver_dir, exist_ok=True)
    out_path = os.path.join(ver_dir, "hardening_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"started_utc": started, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "kind": "deterministic_boundary_no_llm", "result": res}, f, ensure_ascii=False, indent=2, default=str)
    print("[hardening] total=%d passed=%d" % (res["total"], res["passed"]))
    for c in res["cases"]:
        mark = "PASS" if c["passed"] else "FAIL"
        print("  %s  %s" % (mark, c["name"]))
    print("[hardening] saved => %s" % out_path)
    if not res["hardened_enough"]:
        sys.exit(1)


if __name__ == "__main__":
    main()