# docx_parser.py
import re
from docx import Document

# 题号：1.  1)  1、 之类
RE_Q_START = re.compile(r"^\s*(\d+)[\.\、\)]")
# 选项：A. xxx
RE_OPT = re.compile(r"^\s*([A-D])[\.\、\)]\s*(.+)")
# 答案：参考答案：A / 答案：对 / 答案：T 等
RE_ANS = re.compile(r"(参考答案|答案)\s*[:：]\s*(.+)")

def detect_section_type(text: str) -> str:
    """
    根据段落内容判断当前大题类型：
    返回:
      "choice"  - 选择题（单选/多选）
      "blank"   - 填空题
      "judge"   - 判断题
      "skip"    - 简答/解答/综合等不要的题型
      ""        - 未识别（保持原类型）
    """
    t = text.strip()
    if "选择题" in t or "单选题" in t or "多选题" in t:
        return "choice"
    if "填空题" in t:
        return "blank"
    if "判断题" in t or "判断下列说法是否正确" in t:
        return "judge"
    if "简答题" in t or "解答题" in t or "论述题" in t or "综合题" in t or "开放题" in t:
        return "skip"
    return ""

def parse_docx(path: str) -> list:
    """
    从 docx 解析题目，返回 Python 字典列表。
    现在支持三种类型：
      - 选择题: type = "single_choice" 或 "multi_choice"
      - 填空题: type = "blank"
      - 判断题: type = "judge"
    输出元素示例：
    {
      "stem": "题干...",
      "type": "single_choice"/"multi_choice"/"blank"/"judge",
      "options": {...} 或 None,
      "raw_answer": "A" / "对" / "T" / "填空内容..."
    }
    """
    doc = Document(path)
    questions = []

    current_section = ""  # "choice" / "blank" / "judge" / "skip" / ""
    cur_q = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # 1. 判断是否是大题标题（选择题/填空题/判断题/简答题等）
        sec = detect_section_type(text)
        if sec:
            current_section = sec
            continue

        # 跳过简答题等不需要的部分
        if current_section == "skip":
            continue

        # 2. 匹配答案行
        m_ans = RE_ANS.search(text)
        if m_ans and cur_q is not None:
            cur_q["raw_answer"] = m_ans.group(2).strip()
            continue

        # 3. 匹配题目起始
        m_q = RE_Q_START.match(text)
        if m_q:
            # 先收尾上一题
            if cur_q and cur_q.get("stem"):
                questions.append(cur_q)

            # 新题
            if current_section == "blank":
                q_type = "blank"
                options = None
            elif current_section == "judge":
                # 判断题：不使用 A/B/C/D 选项，直接用题干+答案判断
                q_type = "judge"
                options = None
            else:
                # 默认归为选择题区域
                q_type = "choice"
                options = {}

            stem_text = text[m_q.end():].strip()
            cur_q = {
                "stem": stem_text,
                "type": q_type,
                "options": options,
                "raw_answer": ""
            }
            continue

        # 4. 在选择题区域内，匹配选项 A/B/C/D
        if current_section == "choice" and cur_q is not None:
            m_opt = RE_OPT.match(text)
            if m_opt and isinstance(cur_q.get("options"), dict):
                key = m_opt.group(1)
                val = m_opt.group(2).strip()
                cur_q["options"][key] = val
                continue

        # 5. 其他文本，如果当前正在处理某一道题，就拼到题干里（处理跨行题干）
        if cur_q is not None:
            cur_q["stem"] += "\n" + text

    # 6. 文档结束，把最后一题加入
    if cur_q and cur_q.get("stem"):
        questions.append(cur_q)

    # 7. 二次遍历：区分单选/多选；判断题类型保持 "judge"
    for q in questions:
        if q["type"] == "choice":
            ans = (q.get("raw_answer") or "").upper().replace("，", "").replace("、", "")
            letters = [ch for ch in ans if ch in "ABCD"]
            if len(letters) > 1:
                q["type"] = "multi_choice"
            else:
                q["type"] = "single_choice"
        # 判断题保持 q["type"] == "judge"，答案里可能是 “对/错”、“T/F”、“True/False”

    return questions
