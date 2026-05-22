"""配置文件"""
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Cookie文件路径
COOKIE_FILE = os.path.join(BASE_DIR, 'cookie.txt')

# 日志目录
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# 结果目录
RESULT_DIR = os.path.join(BASE_DIR, 'results')

# 默认请求参数
DEFAULT_PAGE_COUNT = 10
DEFAULT_PER_PAGE = 20

# 请求间隔（秒）
REQUEST_DELAY = 1.5

# 支持的平台
PLATFORMS = {
    'douyin': '抖音',
    'kuaishou': '快手',
    'xiaohongshu': '小红书',
    'bilibili': 'B站',
}

# 功能类型
FUNC_TYPES = {
    'search_videos': '搜索视频采集',
    'search_comments': '搜索评论采集',
    'video_comments': '作品链接评论采集',
    'user_posts': '主页作品采集',
}