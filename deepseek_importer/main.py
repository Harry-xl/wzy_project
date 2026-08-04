# main.py
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from config import (
    MAX_WORKERS,
    BATCH_SIZE,
    CHECKPOINT_FILE,
    FAILED_FILE,
    build_prompt
)
from llm_parser import parse_docx_with_llm
from llm_client import call_deepseek
from mapper import format_problem_row
from db import insert_problems_batch

# 新增：用来缓存阶段1提取出的原始题目
EXTRACTED_CACHE_FILE = "extracted_questions_cache.json"

def load_checkpoint():
    if not os.path.exists(CHECKPOINT_FILE):
        return {
            "last_completed_index": 0,
            "total_questions": 0,
            "docx_path": ""
        }
    with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_checkpoint(last_completed_index, total_questions, docx_path):
    data = {
        "last_completed_index": last_completed_index,
        "total_questions": total_questions,
        "docx_path": docx_path
    }
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_failed_question(item):
    failed = []
    if os.path.exists(FAILED_FILE):
        with open(FAILED_FILE, "r", encoding="utf-8") as f:
            try:
                failed = json.load(f)
            except Exception:
                failed = []

    failed.append(item)

    with open(FAILED_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)


def chunk_list(data, batch_size):
    for i in range(0, len(data), batch_size):
        yield i, data[i:i + batch_size]


def process_single_question(args):
    global_index, q = args
    prompt = build_prompt(q)
    llm_res = call_deepseek(prompt)
    row = format_problem_row(q, global_index, llm_res)
    return row


def process_one_batch(batch_questions, start_global_index, overall_pbar, stats):
    rows = []
    errors = []

    tasks = [(start_global_index + i, q) for i, q in enumerate(batch_questions)]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(process_single_question, t): t for t in tasks}

        for future in as_completed(future_map):
            task = future_map[future]
            global_index, q = task
            try:
                row = future.result()
                rows.append(row)
                stats["success"] += 1
            except Exception as e:
                errors.append({
                    "global_index": global_index,
                    "question": q,
                    "error": str(e)
                })
                stats["failed"] += 1

            overall_pbar.update(1)
            overall_pbar.set_postfix({
                "成功": stats["success"],
                "失败": stats["failed"],
                "已写库": stats["inserted"]
            })

    rows.sort(key=lambda x: x[0])
    return rows, errors


def print_banner(title: str):
    print("\n" + "=" * 55)
    print(f"  {title}")
    print("=" * 55)


def main(docx_path: str):
    total_start = time.time()

    print_banner("🚀 题库导入工具 启动")
    print(f"文档路径: {docx_path}\n")

    # ========= 【优化】阶段 1：带缓存的提取逻辑 =========
    questions = []
    # 检查是否有提取成功的缓存文件
    if os.path.exists(EXTRACTED_CACHE_FILE):
        try:
            with open(EXTRACTED_CACHE_FILE, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
            if cached_data.get("docx_path") == docx_path and len(cached_data.get("questions", [])) > 0:
                print(f"♻️ 发现阶段1缓存文件！直接读取已提取的 {len(cached_data['questions'])} 道题，跳过漫长的提取过程。")
                questions = cached_data["questions"]
        except Exception as e:
            print(f"读取缓存失败: {e}，将重新提取。")

    # 如果没有缓存，或者缓存对不上，就真正去请求 LLM
    if not questions:
        questions = parse_docx_with_llm(docx_path)
        if questions:
            # 提取完后立刻保存下来，以后再崩也不怕了
            with open(EXTRACTED_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"docx_path": docx_path, "questions": questions}, f, ensure_ascii=False, indent=2)
            print(f"💾 阶段1提取结果已缓存至 {EXTRACTED_CACHE_FILE}")
    # ====================================================

    total_questions = len(questions)
    if total_questions == 0:
        print("⚠️ 没有解析到可导入题目，请检查文档格式")
        return

    checkpoint = load_checkpoint()
    last_completed_index = 0

    if checkpoint.get("docx_path") == docx_path and checkpoint.get("total_questions") == total_questions:
        last_completed_index = checkpoint.get("last_completed_index", 0)
        if last_completed_index > 0:
            print(f"📌 检测到断点，从第 {last_completed_index + 1} 题继续\n")
    else:
        save_checkpoint(0, total_questions, docx_path)

    remaining_questions = questions[last_completed_index:]

    if not remaining_questions:
        print("✅ 该文档已经全部导入完成！")
        return

    remaining_count = len(remaining_questions)

    print_banner("【阶段 2/2】 AI 标注 + 写入数据库")
    print(f"待处理题目：{remaining_count} 道 | 并发线程：{MAX_WORKERS} | 每批：{BATCH_SIZE} 题\n")

    stats = {"success": 0, "failed": 0, "inserted": 0}
    completed = last_completed_index

    with tqdm(
        total=remaining_count,
        desc="🤖 标注进度",
        unit="题",
        ncols=80,
        colour="green"
    ) as overall_pbar:

        for batch_offset, batch_questions in chunk_list(remaining_questions, BATCH_SIZE):
            batch_start = last_completed_index + batch_offset + 1
            batch_end = batch_start + len(batch_questions) - 1

            rows, errors = process_one_batch(batch_questions, batch_start, overall_pbar, stats)

            if rows:
                inserted = insert_problems_batch(rows)
                stats["inserted"] += inserted

            if errors:
                for err in errors:
                    append_failed_question(err)

            completed = batch_end
            save_checkpoint(completed, total_questions, docx_path)

    elapsed = time.time() - total_start
    minutes, seconds = divmod(int(elapsed), 60)

    print_banner("🎉 导入完成！统计报告")
    print(f"文档总题目：   {total_questions} 道")
    print(f"本次处理：     {remaining_count} 道")
    print(f"成功标注：     {stats['success']} 道")
    print(f"标注失败：     {stats['failed']} 道")
    print(f"写入数据库：   {stats['inserted']} 条")
    if stats["failed"] > 0:
        print(f"失败记录文件： {FAILED_FILE}")
    print(f"总耗时：       {minutes} 分 {seconds} 秒")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    import os
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DOCX_FILE = os.path.join(BASE_DIR, "problem.docx")
    main(DOCX_FILE)
