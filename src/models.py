"""
Data models for Daily Briefing
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class Category(Enum):
    AI = "ai"
    ROBOTICS = "robotics"
    EMBODIED_AI = "embodied_ai"
    SEMICONDUCTOR = "semiconductor"
    AUTO = "auto"
    HEALTH = "health"
    ECONOMY = "economy"
    BUSINESS = "business"
    POLITICS = "politics"
    INVESTMENT = "investment"
    CONSUMER_ELECTRONICS = "consumer_electronics"
    KEY_PEOPLE = "key_people"


@dataclass
class NewsSource:
    """新闻源"""
    name: str
    url: str
    source_type: str  # rss, web
    language: str
    rss_url: Optional[str] = None
    region: Optional[str] = None


@dataclass
class RawArticle:
    """原始文章（采集后）"""
    id: str
    title: str
    url: str
    source: str
    source_url: str
    published_at: datetime
    content: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    image_urls: list[str] = field(default_factory=list)
    video_urls: list[str] = field(default_factory=list)
    language: str = "en"
    raw_html: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.now)


@dataclass
class ProcessedArticle:
    """处理后的文章"""
    id: str
    title_original: str
    title_zh: str
    url: str
    source: str
    published_at: datetime
    
    # 分类
    category: Category
    category_confidence: float
    
    # 内容
    summary_zh: str  # 详细中文摘要
    key_points: list[str]  # 关键要点
    impact_analysis: str  # 影响分析
    
    # 媒体
    images: list[str]  # 本地图片路径
    video_urls: list[str]
    
    # 元数据
    language: str
    is_primary: bool = True  # 是否为该事件的首发报道
    related_event_id: Optional[str] = None  # 关联的事件ID（用于去重）
    mentioned_people: list[str] = field(default_factory=list)
    source_count: int = 1  # 报道该事件的来源数量（去重时更新）
    
    processed_at: datetime = field(default_factory=datetime.now)


@dataclass
class NewsEvent:
    """新闻事件（用于去重合并）"""
    id: str
    title: str
    articles: list[ProcessedArticle]
    first_seen: datetime
    category: Category
    importance: float  # 0-1
    

@dataclass 
class Prediction:
    """预测"""
    category: Category
    timeframe: str  # week, month, half_year, year
    content: str
    created_at: datetime
    

@dataclass
class PredictionChange:
    """预测变化"""
    category: Category
    timeframe: str
    old_content: str
    new_content: str
    reason: str
    changed_at: datetime


@dataclass
class DailyBriefing:
    """每日简报"""
    date: datetime
    articles_by_category: dict[Category, list[ProcessedArticle]]
    predictions: list[Prediction]
    prediction_changes: list[PredictionChange]
    summary: str  # 今日概览
    generated_at: datetime = field(default_factory=datetime.now)
