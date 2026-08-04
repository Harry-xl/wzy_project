# mapper.py
from config import STANDARD_KNOWLEDGE_POINTS, OSI_LAYERS

def normalize_answer(ans: str, q_type: str) -> str:
    ans = (ans or "").strip()

    if q_type == "judge":
        mapping = {
            "正确": "对",
            "错误": "错",
            "T": "对",
            "F": "错",
            "TRUE": "对",
            "FALSE": "错",
            "YES": "对",
            "NO": "错"
        }
        upper_ans = ans.upper()
        if upper_ans in mapping:
            return mapping[upper_ans]
        if ans in mapping:
            return mapping[ans]
    return ans

def normalize_osi_layer(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return None

    v = value.strip()
    if not v:
        return None

    v = v.replace("层级：", "").replace("OSI层：", "").replace("OSI层", "")
    v = v.replace("。", "").replace(".", "").replace("，", "").replace(",", "")

    if "应用层" in v:
        return "应用层"
    if "表示层" in v:
        return "表示层"
    if "会话层" in v:
        return "会话层"
    if "传输层" in v:
        return "传输层"
    if "网络层" in v:
        return "网络层"
    if "数据链路层" in v:
        return "数据链路层"
    if "物理层" in v:
        return "物理层"

    return None

def format_problem_row(q: dict, q_index: int, llm_res: dict) -> tuple:
    problem_num = f"NET-{q_index:05d}"

    problem_text = q["stem"].strip()
    if q.get("options"):
        options_text = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
        problem_text = f"{problem_text}\n{options_text}"

    answer = normalize_answer(q.get("answer") or q.get("raw_answer", ""), q.get("type", ""))

    difficulty = (llm_res.get("difficulty") or "中等").strip()
    if difficulty not in ["简单", "中等", "困难"]:
        difficulty = "中等"

    knowledge_point = (llm_res.get("knowledge_point") or "").strip()
    if knowledge_point not in STANDARD_KNOWLEDGE_POINTS:
        knowledge_point = "计算机网络概述"

    osi_layer = normalize_osi_layer(llm_res.get("osi_layer"))

    return (
        problem_num,
        problem_text,
        answer,
        difficulty,
        knowledge_point,
        osi_layer
    )
