"""
Daily Briefing Web - 每日全球科技简报网站

基于 Flask 的简报阅读网站
"""

from flask import Flask, render_template, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
from pathlib import Path
import json
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 数据目录
DATA_DIR = Path(__file__).parent.parent / 'data'
OUTPUT_DIR = Path(__file__).parent.parent / 'output'


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
    return render_template('index.html', dates=dates, latest_date=latest_date, latest_briefing=latest_briefing)


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


# 健康检查
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
