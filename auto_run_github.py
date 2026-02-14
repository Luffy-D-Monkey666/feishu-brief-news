#!/usr/bin/env python3
"""
GitHub Actions 版本的每日简报生成脚本

与 auto_run.py 类似，但不包含 git push（由 GitHub Actions 处理）
"""

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# 设置环境变量（GitHub Actions 会注入）
# 无需 dotenv

sys.path.insert(0, str(Path(__file__).parent / "src"))

from models import Category, DailyBriefing
from collector import NewsCollector
from processor import NewsProcessor
from predictor import Predictor
from generator import MarkdownGenerator
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")


def save_briefing_json(briefing: DailyBriefing, date_str: str) -> Path:
    """保存简报为JSON格式"""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    articles_by_category = {}
    for category, articles in briefing.articles_by_category.items():
        cat_key = category.value if hasattr(category, 'value') else str(category)
        articles_by_category[cat_key] = []
        for article in articles:
            articles_by_category[cat_key].append({
                'id': article.id,
                'title_original': article.title_original,
                'title_zh': article.title_zh,
                'source': article.source,
                'published_at': article.published_at.strftime('%Y-%m-%d %H:%M') if hasattr(article.published_at, 'strftime') else str(article.published_at),
                'url': article.url,
                'summary_zh': article.summary_zh,
                'key_points': article.key_points,
                'impact_analysis': article.impact_analysis,
                'mentioned_people': article.mentioned_people,
                'category': cat_key
            })
    
    predictions = []
    category_names = {
        'ai': 'AI类', 'robotics': '机器人类', 'embodied_ai': '具身智能类',
        'semiconductor': '半导体行业类', 'auto': '汽车类', 'health': '健康医疗类',
        'economy': '经济政策类', 'business': '商业科技类', 'politics': '政治政策类',
        'investment': '投资财经类', 'consumer_electronics': '消费电子类', 'key_people': '关键人物发言'
    }
    
    for pred in briefing.predictions:
        cat_key = pred.category.value if hasattr(pred.category, 'value') else str(pred.category)
        predictions.append({
            'category': cat_key,
            'category_name': category_names.get(cat_key, cat_key),
            'timeframe': pred.timeframe,
            'content': pred.content
        })
    
    total_articles = sum(len(articles) for articles in articles_by_category.values())
    categories_count = sum(1 for articles in articles_by_category.values() if articles)
    
    sources = set()
    for articles in articles_by_category.values():
        for article in articles:
            sources.add(article['source'])
    
    data = {
        'date': date_str,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_articles': total_articles,
        'categories_count': categories_count,
        'sources_count': len(sources),
        'summary': briefing.summary,
        'articles_by_category': articles_by_category,
        'predictions': predictions
    }
    
    json_path = data_dir / f"briefing_{date_str}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved JSON to {json_path}")
    return json_path


async def run_daily_briefing():
    """执行每日简报生成"""
    
    target_date = datetime.now() - timedelta(days=1)
    date_str = target_date.strftime('%Y%m%d')
    
    logger.info(f"===== Daily Briefing for {target_date.strftime('%Y-%m-%d')} =====")
    
    since = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    until = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Step 1: 采集
    logger.info("Step 1: Collecting news...")
    collector = NewsCollector(config_path=str(Path(__file__).parent / "config/sources.yaml"))
    raw_articles = await collector.collect_all(since)
    await collector.close()
    
    raw_articles = [a for a in raw_articles if since <= a.published_at <= until]
    logger.info(f"Collected {len(raw_articles)} articles")
    
    if not raw_articles:
        logger.warning("No articles found!")
        return None
    
    # 限制处理数量
    MAX_ARTICLES = 50
    if len(raw_articles) > MAX_ARTICLES:
        raw_articles = sorted(raw_articles, key=lambda x: x.published_at, reverse=True)[:MAX_ARTICLES]
        logger.info(f"Limited to {MAX_ARTICLES} most recent articles")
    
    # Step 2: 处理
    logger.info("Step 2: Processing articles...")
    processor = NewsProcessor(
        categories_config=str(Path(__file__).parent / "config/categories.yaml"),
        people_config=str(Path(__file__).parent / "config/key_people.yaml")
    )
    processed_articles = await processor.process_all(raw_articles)
    logger.info(f"Processed {len(processed_articles)} articles")
    
    articles_by_category = {category: [] for category in Category}
    for article in processed_articles:
        articles_by_category[article.category].append(article)
    
    for category in articles_by_category:
        articles_by_category[category].sort(key=lambda x: x.published_at, reverse=True)
    
    # Step 3: 预测
    logger.info("Step 3: Generating predictions...")
    predictor = Predictor(history_path=str(Path(__file__).parent / "data/predictions_history.json"))
    predictions, changes = await predictor.predict_all(articles_by_category)
    logger.info(f"Generated {len(predictions)} predictions")
    
    # 生成摘要
    summary_parts = []
    for category, articles in articles_by_category.items():
        if articles:
            summary_parts.append(f"{articles[0].title_zh[:40]}")
    summary = "今日要闻：" + "；".join(summary_parts[:5]) + "。" if summary_parts else "今日暂无重大新闻。"
    
    briefing = DailyBriefing(
        date=target_date,
        articles_by_category=articles_by_category,
        predictions=predictions,
        prediction_changes=changes,
        summary=summary
    )
    
    # Step 4: 保存JSON
    logger.info("Step 4: Saving JSON...")
    json_path = save_briefing_json(briefing, date_str)
    
    # Step 5: 生成Markdown
    logger.info("Step 5: Generating Markdown...")
    md_generator = MarkdownGenerator(output_dir=str(Path(__file__).parent / "output"))
    md_path = md_generator.save(briefing)
    logger.info(f"Saved Markdown to {md_path}")
    
    total = sum(len(articles) for articles in articles_by_category.values())
    categories_with_content = sum(1 for articles in articles_by_category.values() if articles)
    
    logger.info(f"""
===== Daily Briefing Complete =====
Date: {target_date.strftime('%Y-%m-%d')}
Total Articles: {total}
Categories: {categories_with_content}/12
JSON: {json_path}
Markdown: {md_path}
===================================
""")
    
    return {
        'date': date_str,
        'total_articles': total,
        'categories': categories_with_content
    }


if __name__ == "__main__":
    # 检查 API Key
    if not os.environ.get('DEEPSEEK_API_KEY'):
        print("ERROR: DEEPSEEK_API_KEY not set")
        sys.exit(1)
    
    result = asyncio.run(run_daily_briefing())
    if result:
        print(f"SUCCESS: {result['total_articles']} articles published")
    else:
        print("FAILED: No output generated")
        sys.exit(1)
