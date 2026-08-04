#!/usr/bin/env python3
"""
PDF OCR 工具 —— 将扫描版 PDF 转换为 Markdown + Word 文档。

针对 400+ 页中文扫描教材设计，特性：
- 断点续传（Ctrl+C 中断后 --resume 继续）
- Mini-batch 处理（充分利用 CPU）
- 流式 Markdown 输出（中断不丢已处理页）
- DOCX 分卷输出（--split N）
- 页面级错误隔离（一页失败不影响全量）

用法:
    python ocr_tool.py 教材.pdf                           # 全量处理
    python ocr_tool.py 教材.pdf --resume                   # 从断点继续
    python ocr_tool.py 教材.pdf --split 100                # 每100页拆分DOCX
    python ocr_tool.py 教材.pdf --start-page 1 --end-page 5 # 测试前5页
    python ocr_tool.py 教材.pdf -f md --dpi 300 -v          # 只输出MD，高精度

依赖安装:
    cd tools/pdf_ocr
    pip install -r requirements.txt
"""

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

# 将工具目录加入 sys.path，以便直接运行此脚本
SCRIPT_DIR = str(Path(__file__).parent.resolve())
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from pdf_processor import PdfProcessor, PdfProcessorError
from ocr_engine import OcrEngine, OcrEngineError
from output_writer import OutputWriter, OutputWriterError
from checkpoint import CheckpointManager

# ---------------------------------------------------------------------------
# 日志配置 (延迟到 main 中按 verbose 模式设置)
# ---------------------------------------------------------------------------

logger = logging.getLogger("pdf_ocr")


def setup_logging(verbose: bool = False):
    """配置日志格式和级别。"""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = (
        '%(asctime)s [%(levelname)-7s] %(message)s'
        if verbose
        else '%(message)s'
    )
    datefmt = '%H:%M:%S' if verbose else None

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger("pdf_ocr")
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

    # 抑制第三方库日志
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("paddleocr").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# 全局状态（用于信号处理）
# ---------------------------------------------------------------------------

_global_state = {
    'ckpt_mgr': None,
    'writer': None,
    'start_time': None,
}


def _signal_handler(signum, frame):
    """SIGINT (Ctrl+C) 处理：保存进度后优雅退出。"""
    sig_name = signal.Signals(signum).name
    logger.warning(f"\n收到 {sig_name} 信号，正在保存进度...")

    ckpt = _global_state.get('ckpt_mgr')
    writer = _global_state.get('writer')

    if ckpt and ckpt.current:
        ckpt._save()  # 强制保存当前进度
        ckpt.print_summary()

    if writer:
        try:
            writer.finalize('both')
        except Exception:
            pass

    elapsed = time.time() - _global_state.get('start_time', time.time())
    logger.info(f"已用时: {elapsed/60:.1f} 分钟")
    logger.info("下次运行: python ocr_tool.py <文件> --resume")

    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI 参数解析
# ---------------------------------------------------------------------------

def parse_args(args: list = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="PDF OCR 工具 — 将扫描版 PDF 转为 Markdown + Word",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python ocr_tool.py 教材.pdf                           # 全量处理（默认200 DPI）
  python ocr_tool.py 教材.pdf --resume                   # 从上次中断处继续
  python ocr_tool.py 教材.pdf --split 100                # 每100页拆分DOCX文件
  python ocr_tool.py 教材.pdf --start-page 1 --end-page 5 # 先测试前5页
  python ocr_tool.py 教材.pdf -f md --dpi 300 -v          # 高精度，只输出MD
        """,
    )

    # 必填参数
    parser.add_argument(
        'input_pdf',
        help='输入的扫描 PDF 文件路径',
    )

    # 输出选项
    parser.add_argument(
        '-o', '--output-dir',
        default=None,
        help='输出目录（默认: 与PDF同级的 output/ 目录）',
    )
    parser.add_argument(
        '-f', '--format',
        choices=['md', 'docx', 'both'],
        default='both',
        help='输出格式（默认: both）',
    )

    # 识别选项
    parser.add_argument(
        '--dpi',
        type=int,
        default=200,
        help='渲染 DPI（默认: 200，范围 72-600。400页建议200）',
    )
    parser.add_argument(
        '--lang',
        choices=['ch', 'en', 'ch_en'],
        default='ch',
        help='识别语言（默认: ch）',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5,
        help='Mini-batch 大小（默认: 5，范围 1-20）',
    )

    # 页面范围
    parser.add_argument(
        '--start-page',
        type=int,
        default=1,
        help='起始页码（默认: 1）',
    )
    parser.add_argument(
        '--end-page',
        type=int,
        default=-1,
        help='结束页码（默认: -1 表示最后一页）',
    )

    # 拆分
    parser.add_argument(
        '--split',
        type=int,
        default=0,
        help='每 N 页拆分为独立文件（默认: 0 不拆分，大文档建议 100）',
    )

    # 断点续传
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        '--resume',
        action='store_true',
        default=None,
        help='自动从上次中断处继续（默认: 检测到进度时询问）',
    )
    resume_group.add_argument(
        '--no-resume',
        action='store_true',
        default=None,
        help='忽略已有进度，重新开始',
    )

    # 显示选项
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='关闭进度条',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='详细日志输出（DEBUG 级别）',
    )

    return parser.parse_args(args)


# ---------------------------------------------------------------------------
# 参数验证
# ---------------------------------------------------------------------------

def validate_args(args: argparse.Namespace):
    """验证参数合法性，非法时打印错误并退出。"""
    errors = []

    # 检查 PDF 文件存在
    if not os.path.isfile(args.input_pdf):
        errors.append(f"PDF 文件不存在: {args.input_pdf}")

    # 检查 DPI 范围
    if args.dpi < 72 or args.dpi > 600:
        errors.append(f"DPI 参数必须在 72-600 之间，当前值: {args.dpi}")

    # 检查 batch_size 范围
    if args.batch_size < 1 or args.batch_size > 20:
        errors.append(f"batch-size 必须在 1-20 之间，当前值: {args.batch_size}")

    # 检查 start_page
    if args.start_page < 1:
        errors.append(f"start-page 必须 >= 1，当前值: {args.start_page}")

    # 检查 end_page（-1 表示最后）
    if args.end_page != -1 and args.end_page < args.start_page:
        errors.append(
            f"end-page ({args.end_page}) 不能小于 start-page ({args.start_page})"
        )

    # 检查 split
    if args.split < 0:
        errors.append(f"split 必须 >= 0，当前值: {args.split}")

    if errors:
        logger.error("参数错误:")
        for e in errors:
            logger.error(f"  ❌ {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# 主管线
# ---------------------------------------------------------------------------

def main(args: argparse.Namespace = None):
    """PDF OCR 主管线。

    流程:
    1. 解析参数 + 验证
    2. 检测断点（询问用户是否继续）
    3. 逐页提取图片 → mini-batch OCR → 流式写入
    4. Ctrl+C 时保存进度并退出
    """
    if args is None:
        args = parse_args()

    setup_logging(verbose=args.verbose)
    validate_args(args)

    # 记录开始时间
    _global_state['start_time'] = time.time()

    # ---- 注册信号处理 ----
    signal.signal(signal.SIGINT, _signal_handler)
    # Windows 也支持 SIGBREAK（Ctrl+Break）
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, _signal_handler)

    # ---- 准备路径 ----
    pdf_basename = Path(args.input_pdf).stem
    if args.output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.abspath(args.input_pdf)),
            'output',
        )
    else:
        output_dir = args.output_dir

    os.makedirs(output_dir, exist_ok=True)

    # ---- 校验 PDF ----
    logger.info(f"正在校验 PDF: {args.input_pdf}")
    valid, err = PdfProcessor.is_valid_pdf(args.input_pdf)
    if not valid:
        logger.error(f"❌ {err}")
        sys.exit(1)

    logger.info(f"DPI: {args.dpi} | 语言: {args.lang} | "
                f"批大小: {args.batch_size} | 输出: {args.format}")

    # ---- 打开 PDF ----
    try:
        processor = PdfProcessor(args.input_pdf, dpi=args.dpi)
    except PdfProcessorError as e:
        logger.error(f"❌ 打开 PDF 失败: {e}")
        sys.exit(1)

    logger.info(f"PDF 有效: {processor.total_pages} 页")

    # ---- 计算页面范围 ----
    end_page = args.end_page if args.end_page > 0 else processor.total_pages
    end_page = min(end_page, processor.total_pages)

    if args.start_page > end_page:
        logger.error(
            f"页面范围无效: start={args.start_page}, end={end_page}"
        )
        sys.exit(1)

    logger.info(f"处理范围: 第 {args.start_page}-{end_page} 页 "
                f"（共 {end_page - args.start_page + 1} 页）")

    # ---- 断点续传 ----
    ckpt_mgr = CheckpointManager(args.input_pdf, output_dir)
    _global_state['ckpt_mgr'] = ckpt_mgr

    existing = ckpt_mgr.load()

    if existing and args.no_resume:
        logger.info("--no-resume 已指定，忽略旧进度，重新开始")
        ckpt_mgr.clear()
        existing = None

    if existing and args.resume is None and args.resume is not False:
        # 检测到进度但未明确指定 --resume → 询问用户
        print()
        print(f"检测到上次处理进度:")
        print(f"  已完成: {existing.completed_count}/{existing.total_pages} 页")
        print(f"  失  败: {existing.failed_count} 页")
        print(f"  进  度: {existing.progress_pct}%")
        print()
        choice = input("是否从断点继续？[Y/n] ").strip().lower()
        if choice == 'n':
            logger.info("用户选择重新开始")
            ckpt_mgr.clear()
            existing = None
        else:
            logger.info("将从断点继续处理")
            args.resume = True
    elif existing and args.resume:
        logger.info(f"将从断点继续（已完成 {existing.completed_count} 页）")

    # 创建或使用已有进度
    if existing:
        # 更新总页数（PDF 可能已变更）
        checkpoint = existing
    else:
        checkpoint = ckpt_mgr.create(processor.total_pages)

    # 计算待处理页
    if existing and args.resume:
        # 断点续传：get_pending_pages 排除已完成页
        pending_pages = ckpt_mgr.get_pending_pages(args.start_page, end_page)
    else:
        # 全新开始
        pending_pages = list(range(args.start_page, end_page + 1))

    if not pending_pages:
        logger.info("✅ 所有页面已处理完成，无需继续")
        ckpt_mgr.print_summary()
        processor.close()
        return

    logger.info(f"待处理: {len(pending_pages)} 页")
    if existing:
        logger.info(f"（已完成 {existing.completed_count} 页 + "
                    f"失败 {existing.failed_count} 页）")

    # ---- 初始化 OCR 引擎 ----
    logger.info("正在初始化 PaddleOCR 引擎（首次运行需下载模型 ~500MB）...")
    try:
        engine = OcrEngine(lang=args.lang)
    except OcrEngineError as e:
        logger.error(f"❌ OCR 引擎初始化失败: {e}")
        sys.exit(1)

    # ---- 初始化输出器 ----
    md_enabled = args.format in ('md', 'both')
    docx_enabled = args.format in ('docx', 'both')
    writer = OutputWriter(
        output_dir=output_dir,
        basename=pdf_basename,
        split_pages=args.split,
        md_enabled=md_enabled,
        docx_enabled=docx_enabled,
    )
    _global_state['writer'] = writer

    # ---- 主处理循环 ----
    total = len(pending_pages)
    batch = []
    batch_nums = []

    try:
        from tqdm import tqdm

        with tqdm(
            total=total,
            unit='页',
            bar_format=(
                '{l_bar}{bar}| {n_fmt}/{total_fmt} 页 '
                '[{elapsed}<{remaining}, {rate_fmt}]'
            ),
            disable=args.no_progress,
        ) as pbar:
            for idx, page_num in enumerate(pending_pages):
                # 提取页面图片
                try:
                    image = processor.extract_page(page_num)
                except PdfProcessorError as e:
                    logger.error(f"第 {page_num} 页提取失败: {e}")
                    ckpt_mgr.mark_failed(page_num, str(e))
                    pbar.update(1)
                    continue

                batch.append(image)
                batch_nums.append(page_num)

                # 批次满 或 最后一页 → 执行 OCR
                is_last = (idx == total - 1)
                if len(batch) >= args.batch_size or is_last:
                    try:
                        results = engine.recognize_batch(batch)
                        for num, blocks in zip(batch_nums, results):
                            writer.write_page(num, blocks)
                            ckpt_mgr.mark_done(num)
                    except OcrEngineError as e:
                        logger.error(f"批次识别失败 (页 {batch_nums}): {e}")
                        for num in batch_nums:
                            ckpt_mgr.mark_failed(num, str(e))
                            # 写入错误标记到 MD
                            writer.write_page(num, [
                                {
                                    'text': f'[OCR 识别失败: {e}]',
                                    'confidence': 0.0,
                                    'bbox': [0, 0, 0, 0],
                                }
                            ])

                    pbar.update(len(batch))
                    batch, batch_nums = [], []

                    # 每 50 页清理 PaddleOCR 缓存
                    if page_num % 50 == 0:
                        engine.clear_cache()

    except Exception as e:
        logger.error(f"处理过程中发生未预期错误: {e}", exc_info=args.verbose)
        logger.info("进度已保存，可使用 --resume 恢复")

    # ---- 完成 ----
    writer.finalize(args.format)
    processor.close()

    elapsed = time.time() - _global_state['start_time']
    logger.info("")
    logger.info(f"✅ 处理完成！总耗时: {elapsed/60:.1f} 分钟")

    ckpt_mgr.print_summary()

    logger.info(f"输出文件:")
    for p in writer.output_paths:
        size_mb = os.path.getsize(p) / (1024 * 1024)
        logger.info(f"  📄 {p} ({size_mb:.1f} MB)")

    logger.info(f"进度文件: {os.path.join(output_dir, '.ocr_checkpoint.json')}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
