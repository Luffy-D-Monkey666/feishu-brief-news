"""
Daily Briefing Web - 每日全球科技简报网站

基于 Flask 的简报阅读网站
"""

from flask import Flask, render_template, jsonify, send_from_directory, request
from flask_cors import CORS
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import sys

# 启动时立即输出，确保 Render 检测到进程活跃
print(f"[{datetime.now().isoformat()}] Flask app initializing...", flush=True)
sys.stdout.flush()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 数据目录
DATA_DIR = Path(__file__).parent.parent / 'data'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'

print(f"[{datetime.now().isoformat()}] DATA_DIR: {DATA_DIR}", flush=True)
print(f"[{datetime.now().isoformat()}] OUTPUT_DIR: {OUTPUT_DIR}", flush=True)


def load_briefing(date_str: str = None) -> dict:
    """加载简报数据"""
    if date_str is None:
        # 默认加载最新的
        date_str = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    
    # 尝试加载 JSON 数据
    json_path = DATA_DIR / f'briefing_{date_str}.json'
    if json_path.exists():
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 如果没有 JSON，尝试从 Markdown 解析（简化版）
    md_path = OUTPUT_DIR / f'briefing_{date_str}.md'
    if md_path.exists():
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            'date': date_str,
            'markdown': content,
            'articles': [],
            'predictions': []
        }
    
    return None


def calc_article_score(article: dict) -> float:
    """计算文章热度分数（用于首页排序）"""
    score = 0.0
    
    # 1. 分类权重：AI、关键人物 > 其他
    category_weights = {
        'ai': 1.5,
        'key_people': 1.4,
        'semiconductor': 1.2,
        'auto': 1.1,
        'robotics': 1.1,
        'politics': 1.0,
        'business': 0.9,
        'consumer_electronics': 0.8,
    }
    category = article.get('category', 'business')
    score += category_weights.get(category, 0.8)
    
    # 2. 提及关键人物加分
    mentioned_people = article.get('mentioned_people', [])
    if mentioned_people:
        score += 0.5 * min(len(mentioned_people), 3)
    
    # 3. 多来源报道加分
    source_count = article.get('source_count', 1)
    if source_count > 1:
        score += 0.3 * min(source_count - 1, 5)
    
    # 4. 来源权威性
    tier1_sources = ['reuters', 'bloomberg', 'wired', 'the verge', 'techcrunch', 
                     '36氪', '财新', '机器之心', '量子位']
    source = article.get('source', '').lower()
    if any(t in source for t in tier1_sources):
        score += 0.3
    
    return score


def get_hot_articles(briefing: dict, limit: int = 8) -> list:
    """获取热点文章（按分数排序）"""
    all_articles = []
    articles_by_category = briefing.get('articles_by_category', {})
    
    for category, articles in articles_by_category.items():
        for article in articles:
            article_copy = article.copy()
            article_copy['_score'] = calc_article_score(article)
            all_articles.append(article_copy)
    
    # 按分数降序排序
    all_articles.sort(key=lambda x: x['_score'], reverse=True)
    
    return all_articles[:limit]


def get_available_dates() -> list:
    """获取所有可用的简报日期"""
    dates = []
    
    # 检查 JSON 文件
    if DATA_DIR.exists():
        for f in DATA_DIR.glob('briefing_*.json'):
            date_str = f.stem.replace('briefing_', '')
            dates.append(date_str)
    
    # 检查 Markdown 文件
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.glob('briefing_*.md'):
            date_str = f.stem.replace('briefing_', '')
            if date_str not in dates:
                dates.append(date_str)
    
    return sorted(dates, reverse=True)


@app.route('/')
def index():
    """首页"""
    dates = get_available_dates()
    latest_date = dates[0] if dates else None
    latest_briefing = load_briefing(latest_date) if latest_date else None
    
    # 计算热点文章排序
    hot_articles = []
    if latest_briefing:
        hot_articles = get_hot_articles(latest_briefing, limit=8)
    
    return render_template('index.html', dates=dates, latest_date=latest_date, 
                          latest_briefing=latest_briefing, hot_articles=hot_articles)


@app.route('/briefing/<date_str>')
def briefing_page(date_str: str):
    """简报页面"""
    briefing = load_briefing(date_str)
    if briefing is None:
        return render_template('404.html'), 404
    dates = get_available_dates()
    return render_template('briefing.html', briefing=briefing, date=date_str, dates=dates)


@app.route('/api/dates')
def api_dates():
    """API: 获取所有日期"""
    return jsonify({'dates': get_available_dates()})


@app.route('/api/briefing/<date_str>')
def api_briefing(date_str: str):
    """API: 获取简报数据"""
    briefing = load_briefing(date_str)
    if briefing is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(briefing)


@app.route('/api/latest')
def api_latest():
    """API: 获取最新简报"""
    dates = get_available_dates()
    if not dates:
        return jsonify({'error': 'No briefings available'}), 404
    return jsonify(load_briefing(dates[0]))


@app.route('/search')
def search_page():
    """搜索页面"""
    query = request.args.get('q', '').strip()
    results = []
    
    if query:
        # 搜索所有日期的简报
        dates = get_available_dates()
        for date_str in dates[:30]:  # 最多搜索最近30天
            briefing = load_briefing(date_str)
            if not briefing:
                continue
            
            articles_by_category = briefing.get('articles_by_category', {})
            for category, articles in articles_by_category.items():
                for article in articles:
                    # 搜索标题和摘要
                    title = (article.get('title_zh', '') + ' ' + article.get('title_original', '')).lower()
                    summary = article.get('summary_zh', '').lower()
                    query_lower = query.lower()
                    
                    if query_lower in title or query_lower in summary:
                        results.append({
                            'article': article,
                            'date': date_str,
                            'match_in': 'title' if query_lower in title else 'summary'
                        })
        
        # 按日期排序（最新优先）
        results.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('search.html', query=query, results=results[:50])


@app.route('/api/search')
def api_search():
    """API: 搜索文章"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': 'Missing query parameter'}), 400
    
    results = []
    dates = get_available_dates()
    
    for date_str in dates[:30]:
        briefing = load_briefing(date_str)
        if not briefing:
            continue
        
        articles_by_category = briefing.get('articles_by_category', {})
        for category, articles in articles_by_category.items():
            for article in articles:
                title = (article.get('title_zh', '') + ' ' + article.get('title_original', '')).lower()
                summary = article.get('summary_zh', '').lower()
                query_lower = query.lower()
                
                if query_lower in title or query_lower in summary:
                    results.append({
                        **article,
                        'date': date_str
                    })
    
    results.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({'query': query, 'count': len(results), 'results': results[:50]})


# 健康检查 - 尽可能轻量
@app.route('/health')
def health():
    return 'ok', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"[{datetime.now().isoformat()}] Starting Flask on port {port}, debug={debug}", flush=True)
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
