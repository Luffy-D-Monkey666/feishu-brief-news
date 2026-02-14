"""
飞书文档格式化器

使用飞书文档块结构，优化简报的可读性：
- 标题层级
- 高亮块（Callout）
- 分割线
- 表格
- 列表
"""

import sys
sys.path.insert(0, "/workspace/openclaw/skills/feishu-doc-operations/scripts")

from feishu_doc_operations import obtainIdaasClientId, obtainIdaasClientSecret, obtainUserName, main as feishu_doc_main


def feishu_operation(params: dict) -> dict:
    """封装飞书文档操作"""
    action = params.get('action')
    
    if action == 'create':
        return feishu_doc_main({
            'action': 'write',
            'title': params.get('title'),
            'content': params.get('content'),
            'folder_token': params.get('folder_token'),
            'client_id': obtainIdaasClientId(),
            'client_secret': obtainIdaasClientSecret(),
            'userName': obtainUserName()
        })
    
    return {'code': -1, 'msg': f'Unsupported action: {action}'}
from datetime import datetime
from typing import Optional


CATEGORY_INFO = {
    'ai': {'name': 'AI类', 'icon': '🤖', 'color': 'blue'},
    'robotics': {'name': '机器人类', 'icon': '🦾', 'color': 'purple'},
    'embodied_ai': {'name': '具身智能类', 'icon': '👓', 'color': 'indigo'},
    'semiconductor': {'name': '半导体行业类', 'icon': '💾', 'color': 'orange'},
    'auto': {'name': '汽车类', 'icon': '🚗', 'color': 'green'},
    'health': {'name': '健康医疗类', 'icon': '🏥', 'color': 'red'},
    'economy': {'name': '经济政策类', 'icon': '📊', 'color': 'yellow'},
    'business': {'name': '商业科技类', 'icon': '💼', 'color': 'turquoise'},
    'politics': {'name': '政治政策类', 'icon': '🏛️', 'color': 'grey'},
    'investment': {'name': '投资财经类', 'icon': '📈', 'color': 'wathet'},
    'consumer_electronics': {'name': '消费电子类', 'icon': '📱', 'color': 'carmine'},
    'key_people': {'name': '关键人物发言', 'icon': '🎤', 'color': 'violet'},
}


def format_article_card(article: dict, index: int, cat_info: dict) -> str:
    """格式化单篇文章为卡片样式的文本块"""
    
    # 使用 Markdown 格式，飞书会自动渲染
    parts = []
    
    # 文章标题（双语）
    parts.append(f"### {index}. {article['title_original']}")
    if article['title_zh'] != article['title_original']:
        parts.append(f"**{article['title_zh']}**")
    parts.append("")
    
    # 元信息行
    meta = f"📰 **{article['source']}** · 🕐 {article['published_at']}"
    if article.get('mentioned_people'):
        meta += f" · 👤 {', '.join(article['mentioned_people'])}"
    parts.append(meta)
    parts.append("")
    
    # 摘要（使用引用格式）
    parts.append("**📋 摘要**")
    parts.append("")
    # 将摘要分段
    summary_paragraphs = article['summary_zh'].split('\n\n')
    for para in summary_paragraphs[:3]:  # 最多3段
        parts.append(f"> {para.strip()}")
        parts.append(">")
    parts.append("")
    
    # 关键要点（使用列表）
    if article.get('key_points'):
        parts.append("**🔑 关键要点**")
        for point in article['key_points'][:4]:  # 最多4点
            parts.append(f"• {point}")
        parts.append("")
    
    # 影响分析（使用高亮块样式）
    if article.get('impact_analysis'):
        parts.append("**📈 影响分析**")
        parts.append(f"💡 {article['impact_analysis'][:300]}...")
        parts.append("")
    
    # 链接
    parts.append(f"🔗 [阅读原文]({article['url']})")
    parts.append("")
    parts.append("---")
    parts.append("")
    
    return '\n'.join(parts)


def format_overview(articles_by_category: dict, date_str: str) -> str:
    """格式化今日概览"""
    
    parts = []
    
    # 标题
    parts.append(f"# 📰 全球科技简报")
    parts.append("")
    parts.append(f"## 📅 {date_str}")
    parts.append("")
    parts.append("---")
    parts.append("")
    
    # 统计卡片
    total = sum(len(articles) for articles in articles_by_category.values())
    categories_with_content = [(cat, articles) for cat, articles in articles_by_category.items() if articles]
    
    parts.append("## 📊 今日概览")
    parts.append("")
    parts.append(f"**共计 {total} 条新闻，覆盖 {len(categories_with_content)} 个类别**")
    parts.append("")
    
    # 分类统计表格
    parts.append("| 类别 | 数量 | 头条 |")
    parts.append("|------|------|------|")
    
    for cat, articles in categories_with_content:
        info = CATEGORY_INFO.get(cat, {'name': cat, 'icon': '📌'})
        headline = articles[0]['title_zh'][:30] + '...' if len(articles[0]['title_zh']) > 30 else articles[0]['title_zh']
        parts.append(f"| {info['icon']} {info['name']} | {len(articles)} | {headline} |")
    
    parts.append("")
    parts.append("---")
    parts.append("")
    
    return '\n'.join(parts)


def format_category_section(category: str, articles: list) -> str:
    """格式化单个分类的新闻"""
    
    if not articles:
        return ""
    
    info = CATEGORY_INFO.get(category, {'name': category, 'icon': '📌', 'color': 'grey'})
    
    parts = []
    parts.append(f"## {info['icon']} {info['name']}")
    parts.append("")
    
    for i, article in enumerate(articles, 1):
        parts.append(format_article_card(article, i, info))
    
    return '\n'.join(parts)


def format_predictions(predictions: list, changes: list) -> str:
    """格式化预测部分"""
    
    parts = []
    parts.append("## 🎯 未来预测")
    parts.append("")
    
    timeframe_names = {
        "week": ("📆 未来一周", "短期"),
        "month": ("📆 未来一个月", "中期"),
        "half_year": ("📆 未来半年", "中长期"),
        "year": ("📆 未来一年", "长期")
    }
    
    for timeframe, (title, desc) in timeframe_names.items():
        tf_predictions = [p for p in predictions if p.get('timeframe') == timeframe]
        tf_changes = {c['category']: c for c in changes if c.get('timeframe') == timeframe}
        
        if not tf_predictions:
            continue
        
        parts.append(f"### {title}")
        parts.append("")
        
        for pred in tf_predictions:
            cat = pred['category']
            info = CATEGORY_INFO.get(cat, {'name': cat, 'icon': '📌'})
            
            parts.append(f"**{info['icon']} {info['name']}**")
            parts.append("")
            
            # 预测内容
            content = pred.get('content', '')[:200]
            parts.append(f"> {content}...")
            parts.append("")
            
            # 变化说明
            if cat in tf_changes:
                change = tf_changes[cat]
                parts.append(f"⬆️ *变化: {change.get('reason', '根据最新信息更新')}*")
                parts.append("")
        
        parts.append("---")
        parts.append("")
    
    return '\n'.join(parts)


def create_feishu_briefing(
    articles_by_category: dict,
    predictions: list,
    changes: list,
    date: datetime,
    folder_token: Optional[str] = None
) -> dict:
    """
    创建格式优化的飞书简报文档
    
    Args:
        articles_by_category: 按分类组织的文章 {category: [article_dict, ...]}
        predictions: 预测列表 [{category, timeframe, content}, ...]
        changes: 预测变化列表
        date: 简报日期
        folder_token: 可选的目标文件夹
    
    Returns:
        {'code': 0, 'data': {'url': '...'}} 或错误信息
    """
    
    date_str = date.strftime("%Y年%m月%d日（%A）")
    
    # 构建完整内容
    content_parts = []
    
    # 概览
    content_parts.append(format_overview(articles_by_category, date_str))
    
    # 各分类新闻
    for category in ['ai', 'robotics', 'embodied_ai', 'semiconductor', 'auto', 
                     'health', 'economy', 'business', 'politics', 'investment',
                     'consumer_electronics', 'key_people']:
        articles = articles_by_category.get(category, [])
        if articles:
            content_parts.append(format_category_section(category, articles))
    
    # 预测
    if predictions:
        content_parts.append(format_predictions(predictions, changes))
    
    # 页脚
    content_parts.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    
    full_content = '\n'.join(content_parts)
    
    # 创建飞书文档
    params = {
        'type': 'doc',
        'action': 'create',
        'title': f'每日全球科技简报 - {date.strftime("%Y-%m-%d")}',
        'content': full_content
    }
    
    if folder_token:
        params['folder_token'] = folder_token
    
    result = feishu_operation(params)
    
    return result


def append_to_feishu_doc(
    doc_url: str,
    articles_by_category: dict,
    predictions: list,
    changes: list,
    date: datetime
) -> dict:
    """
    向已有飞书文档追加内容
    """
    
    date_str = date.strftime("%Y年%m月%d日（%A）")
    
    # 构建追加内容
    content_parts = []
    
    # 日期分隔
    content_parts.append("")
    content_parts.append("---")
    content_parts.append("")
    content_parts.append(f"# 📅 {date_str}")
    content_parts.append("")
    
    # 概览
    content_parts.append(format_overview(articles_by_category, date_str))
    
    # 各分类新闻
    for category in ['ai', 'robotics', 'embodied_ai', 'semiconductor', 'auto', 
                     'health', 'economy', 'business', 'politics', 'investment',
                     'consumer_electronics', 'key_people']:
        articles = articles_by_category.get(category, [])
        if articles:
            content_parts.append(format_category_section(category, articles))
    
    # 预测
    if predictions:
        content_parts.append(format_predictions(predictions, changes))
    
    full_content = '\n'.join(content_parts)
    
    # 追加到文档
    result = feishu_operation({
        'type': 'doc',
        'action': 'append',
        'url': doc_url,
        'content': full_content
    })
    
    return result


# 测试
if __name__ == "__main__":
    # 模拟数据
    test_articles = {
        'ai': [{
            'title_original': 'OpenAI Releases GPT-5',
            'title_zh': 'OpenAI发布GPT-5',
            'source': 'TechCrunch',
            'published_at': '2026-02-13 09:30',
            'url': 'https://example.com',
            'summary_zh': '这是一条测试新闻摘要...',
            'key_points': ['要点1', '要点2'],
            'impact_analysis': '影响分析...',
            'mentioned_people': ['Sam Altman']
        }]
    }
    
    test_predictions = [{
        'category': 'ai',
        'timeframe': 'week',
        'content': '关注GPT-5后续市场反应...'
    }]
    
    result = create_feishu_briefing(
        test_articles,
        test_predictions,
        [],
        datetime.now()
    )
    
    print(result)
