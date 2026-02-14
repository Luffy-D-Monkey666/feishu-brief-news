"""
Daily Briefing - 主程序

每日执行流程:
1. 采集前一天的新闻
2. 处理、翻译、分类、去重
3. 生成预测
4. 输出飞书文档和Markdown
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys
from loguru import logger

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from models import Category, DailyBriefing
from collector import NewsCollector
from processor import NewsProcessor
from predictor import Predictor
from generator import MarkdownGenerator, FeishuGenerator


# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
)
logger.add(
    "logs/briefing_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days"
)


async def generate_daily_summary(articles_by_category: dict) -> str:
    """生成今日概览摘要"""
    # 简单实现：列出每个分类的头条
    summary_parts = []
    
    for category, articles in articles_by_category.items():
        if articles:
            top_article = articles[0]
            summary_parts.append(f"• {top_article.title_zh}")
    
    if summary_parts:
        return "今日要闻：\n" + "\n".join(summary_parts[:5])
    return "今日暂无重大新闻。"


async def run_daily_briefing(
    target_date: datetime = None,
    output_dir: str = "output",
    skip_feishu: bool = False
):
    """执行每日简报生成"""
    
    if target_date is None:
        # 默认获取昨天的新闻
        target_date = datetime.now() - timedelta(days=1)
    
    logger.info(f"Starting daily briefing for {target_date.strftime('%Y-%m-%d')}")
    
    # 设置时间范围：目标日期的00:00到23:59
    since = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    until = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Step 1: 采集新闻
    logger.info("Step 1: Collecting news...")
    collector = NewsCollector()
    raw_articles = await collector.collect_all(since)
    await collector.close()
    
    # 过滤时间范围
    raw_articles = [a for a in raw_articles if since <= a.published_at <= until]
    logger.info(f"Collected {len(raw_articles)} articles within time range")
    
    if not raw_articles:
        logger.warning("No articles found for the target date")
        return None
    
    # Step 2: 处理新闻
    logger.info("Step 2: Processing articles...")
    processor = NewsProcessor()
    processed_articles = await processor.process_all(raw_articles)
    logger.info(f"Processed {len(processed_articles)} articles")
    
    # 按分类整理
    articles_by_category = {category: [] for category in Category}
    for article in processed_articles:
        articles_by_category[article.category].append(article)
    
    # 每个分类内按时间排序
    for category in articles_by_category:
        articles_by_category[category].sort(key=lambda x: x.published_at, reverse=True)
    
    # Step 3: 生成预测
    logger.info("Step 3: Generating predictions...")
    predictor = Predictor()
    predictions, changes = await predictor.predict_all(articles_by_category)
    logger.info(f"Generated {len(predictions)} predictions, {len(changes)} changes")
    
    # Step 4: 生成今日概览
    summary = await generate_daily_summary(articles_by_category)
    
    # 构建每日简报对象
    briefing = DailyBriefing(
        date=target_date,
        articles_by_category=articles_by_category,
        predictions=predictions,
        prediction_changes=changes,
        summary=summary
    )
    
    # Step 5: 生成输出
    logger.info("Step 5: Generating outputs...")
    
    # Markdown
    md_generator = MarkdownGenerator(output_dir)
    md_path = md_generator.save(briefing)
    logger.info(f"Markdown saved to {md_path}")
    
    # 飞书文档
    if not skip_feishu:
        try:
            feishu_generator = FeishuGenerator()
            doc_url = await feishu_generator.generate(briefing)
            if doc_url:
                logger.info(f"Feishu document: {doc_url}")
        except Exception as e:
            logger.error(f"Failed to generate Feishu document: {e}")
    
    # 统计
    total_articles = sum(len(articles) for articles in articles_by_category.values())
    categories_with_content = sum(1 for articles in articles_by_category.values() if articles)
    
    logger.info(f"""
===== Daily Briefing Complete =====
Date: {target_date.strftime('%Y-%m-%d')}
Total Articles: {total_articles}
Categories: {categories_with_content}/12
Predictions: {len(predictions)}
Changes: {len(changes)}
Output: {md_path}
===================================
""")
    
    return briefing


async def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Tech Briefing Generator")
    parser.add_argument(
        "--date",
        type=str,
        help="Target date (YYYY-MM-DD), default: yesterday"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Output directory"
    )
    parser.add_argument(
        "--skip-feishu",
        action="store_true",
        help="Skip Feishu document generation"
    )
    
    args = parser.parse_args()
    
    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")
    
    await run_daily_briefing(
        target_date=target_date,
        output_dir=args.output,
        skip_feishu=args.skip_feishu
    )


if __name__ == "__main__":
    asyncio.run(main())
