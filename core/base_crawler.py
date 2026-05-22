"""爬虫基类 - 通用协议接口"""
import os
import time
from abc import ABC, abstractmethod
from utils.logger import log
from utils.storage import StorageUtil
from utils.request import RequestUtil


class BaseCrawler(ABC):
    """爬虫基类，定义通用接口"""

    PLATFORM_NAME = "base"

    def __init__(self, cookie=None):
        self.request = RequestUtil(cookie=cookie)
        self.storage = StorageUtil()
        self.cookie = cookie
        self.is_running = True
        self.total_count = 0

    def set_cookie(self, cookie):
        """设置Cookie"""
        self.cookie = cookie
        self.request.set_cookie(cookie)

    def stop(self):
        """停止采集"""
        self.is_running = False

    def reset(self):
        """重置状态"""
        self.is_running = True
        self.total_count = 0

    @abstractmethod
    def search_videos(self, keyword, page_count=10, per_page=20):
        """
        搜索视频

        Args:
            keyword: 搜索关键词
            page_count: 采集页数
            per_page: 每页数量
        Returns:
            视频列表
        """
        pass

    @abstractmethod
    def get_comments(self, video_id, page_count=10, per_page=20):
        """
        获取视频评论

        Args:
            video_id: 视频ID
            page_count: 采集页数
            per_page: 每页数量
        Returns:
            评论列表
        """
        pass

    @abstractmethod
    def get_user_posts(self, user_url, page_count=10, per_page=20):
        """
        获取用户主页作品

        Args:
            user_url: 用户主页链接
            page_count: 采集页数
            per_page: 每页数量
        Returns:
            作品列表
        """
        pass

    @abstractmethod
    def parse_search_result(self, data):
        """解析搜索结果"""
        pass

    @abstractmethod
    def parse_comment_data(self, data):
        """解析评论数据"""
        pass

    @abstractmethod
    def parse_post_data(self, data):
        """解析作品数据"""
        pass

    def search_and_collect_comments(self, keyword, page_count=10, per_page=20, callback=None):
        """
        搜索视频并采集评论

        Args:
            keyword: 搜索关键词
            page_count: 采集页数
            per_page: 每页数量
            callback: 进度回调函数
        Returns:
            评论总数
        """
        log.info(f'开始搜索关键词: {keyword}')

        # 1. 搜索视频
        videos = self.search_videos(keyword, page_count=1, per_page=per_page)
        if not videos:
            log.warning('未搜索到相关视频')
            return 0

        log.info(f'搜索到 {len(videos)} 个视频')

        # 2. 采集每个视频的评论
        total_comments = []
        for i, video in enumerate(videos[:page_count]):
            if not self.is_running:
                log.info('用户停止采集')
                break

            video_id = video.get('video_id')
            log.info(f'采集视频 [{i+1}/{len(videos)}] {video_id}')

            comments = self.get_comments(video_id, page_count=page_count, per_page=per_page)
            total_comments.extend(comments)

            if callback:
                callback(i + 1, len(videos), len(total_comments))

            # 保存评论
            filename = self.storage.get_timestamp_filename('comments')
            self.storage.save_csv(comments, filename, self.get_comment_fields())
            log.info(f'已保存 {len(comments)} 条评论')

        self.total_count = len(total_comments)
        log.info(f'采集完成，共 {self.total_count} 条评论')

        return self.total_count

    def collect_comments_from_video(self, video_url, page_count=10, per_page=20, callback=None):
        """
        从视频链接采集评论

        Args:
            video_url: 视频链接
            page_count: 采集页数
            per_page: 每页数量
            callback: 进度回调函数
        Returns:
            评论总数
        """
        from utils.parser import ParserUtil

        video_id = ParserUtil.extract_video_id(video_url)
        if not video_id:
            log.error(f'无法解析视频ID: {video_url}')
            return 0

        log.info(f'开始采集视频评论: {video_id}')

        comments = self.get_comments(video_id, page_count=page_count, per_page=per_page)

        if callback:
            callback(page_count, page_count, len(comments))

        # 保存评论
        filename = self.storage.get_timestamp_filename('comments')
        self.storage.save_csv(comments, filename, self.get_comment_fields())

        self.total_count = len(comments)
        log.info(f'采集完成，共 {self.total_count} 条评论')

        return self.total_count

    def collect_user_posts(self, user_url, page_count=10, per_page=20, callback=None):
        """
        采集用户主页作品

        Args:
            user_url: 用户主页链接
            page_count: 采集页数
            per_page: 每页数量
            callback: 进度回调函数
        Returns:
            作品总数
        """
        log.info(f'开始采集用户主页: {user_url}')

        posts = self.get_user_posts(user_url, page_count=page_count, per_page=per_page)

        if callback:
            callback(page_count, page_count, len(posts))

        # 保存作品数据
        filename = self.storage.get_timestamp_filename('posts')
        self.storage.save_csv(posts, filename, self.get_post_fields())
        self.storage.save_json(posts, filename)

        self.total_count = len(posts)
        log.info(f'采集完成，共 {self.total_count} 条作品')

        return self.total_count

    def get_comment_fields(self):
        """评论数据字段"""
        return [
            'video_id', 'video_title', 'video_link',
            'author_name', 'author_id', 'author_uid', 'author_link',
            'comment_time', 'comment_ip', 'comment_like',
            'comment_level', 'comment_text'
        ]

    def get_post_fields(self):
        """作品数据字段"""
        return [
            'page', 'author_name', 'author_uid', 'author_link', 'author_fans',
            'video_title', 'video_tags', 'video_link', 'video_id',
            'publish_time', 'video_duration', 'is_pinned',
            'like_count', 'comment_count', 'collect_count', 'share_count'
        ]

    def close(self):
        """关闭资源"""
        self.request.close()