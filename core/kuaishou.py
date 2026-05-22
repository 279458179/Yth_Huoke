"""快手爬虫实现（预留扩展）"""
from .base_crawler import BaseCrawler
from utils.logger import log


class KuaishouCrawler(BaseCrawler):
    """快手平台爬虫"""

    PLATFORM_NAME = "kuaishou"

    def __init__(self, cookie=None):
        super().__init__(cookie)
        # TODO: 实现快手平台接口

    def search_videos(self, keyword, page_count=10, per_page=20):
        """搜索视频 - 待实现"""
        log.warning("快手平台暂未实现")
        return []

    def get_comments(self, video_id, page_count=10, per_page=20):
        """获取视频评论 - 待实现"""
        log.warning("快手平台暂未实现")
        return []

    def get_user_posts(self, user_url, page_count=10, per_page=20):
        """获取用户主页作品 - 待实现"""
        log.warning("快手平台暂未实现")
        return []

    def parse_search_result(self, data):
        """解析搜索结果 - 待实现"""
        return []

    def parse_comment_data(self, data):
        """解析评论数据 - 待实现"""
        return []

    def parse_post_data(self, data):
        """解析作品数据 - 待实现"""
        return []