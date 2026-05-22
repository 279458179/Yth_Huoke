"""抖音爬虫实现"""
import re
import time
import random
from .base_crawler import BaseCrawler
from utils.logger import log
from utils.parser import ParserUtil


class DouyinCrawler(BaseCrawler):
    """抖音平台爬虫"""

    PLATFORM_NAME = "douyin"

    # 抖音API接口
    API_BASE = "https://www.douyin.com/aweme/v1/web"

    # 搜索视频接口
    SEARCH_API = f"{API_BASE}/search/"

    # 评论列表接口
    COMMENT_API = f"{API_BASE}/comment/list/"

    # 用户主页作品接口
    USER_POST_API = f"{API_BASE}/user/post/"

    def __init__(self, cookie=None):
        super().__init__(cookie)
        self.request.set_referer("https://www.douyin.com/")

    def _get_common_params(self):
        """获取通用请求参数"""
        return {
            'device_platform': 'webapp',
            'aid': '6383',
            'channel_name': 'web_channel_all',
            'pc_client_type': '1',
            'version_code': '170400',
            'version_name': '17.4.0',
            'cookie_enabled': 'true',
            'browser_language': 'zh-CN',
            'browser_platform': 'Win32',
            'browser_name': 'Chrome',
            'browser_version': '120.0.0.0',
            'browser_online': 'true',
            'engine_name': 'Blink',
            'engine_version': '120.0.0.0',
            'os_name': 'Windows',
            'os_version': '10',
            'platform': 'PC',
            'core28': '1',
        }

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
        videos = []

        for page in range(page_count):
            if not self.is_running:
                break

            offset = page * per_page

            params = self._get_common_params()
            params.update({
                'keyword': keyword,
                'offset': offset,
                'count': per_page,
                'search_source': 'normal_search',
                'search_type': 'video',  # 搜索视频
                'sort_type': '0',
                'publish_time': '0',
                'filter_duration': '0',
            })

            log.info(f'搜索第 {page + 1} 页')

            try:
                data = self.request.get(self.SEARCH_API, params=params)

                if data and 'data' in data:
                    video_list = self.parse_search_result(data)
                    videos.extend(video_list)
                    log.info(f'第 {page + 1} 页获取 {len(video_list)} 个视频')

                    # 检查是否还有更多数据
                    if not data.get('has_more', True):
                        log.info('已获取全部数据')
                        break
                else:
                    log.warning(f'第 {page + 1} 页数据为空或请求失败')
                    # 如果连续失败，可能是需要签名参数
                    break

            except Exception as e:
                log.error(f'搜索异常: {e}')
                break

            # 随机延时
            time.sleep(random.uniform(1, 2))

        return videos

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
        comments = []
        cursor = 0

        for page in range(page_count):
            if not self.is_running:
                break

            params = self._get_common_params()
            params.update({
                'aweme_id': video_id,
                'cursor': cursor,
                'count': per_page,
                'comment_style': '2',
            })

            log.info(f'采集视频 {video_id} 第 {page + 1} 页评论')

            try:
                data = self.request.get(self.COMMENT_API, params=params)

                if data and 'comments' in data:
                    comment_list = self.parse_comment_data(data, video_id)
                    comments.extend(comment_list)
                    log.info(f'第 {page + 1} 页获取 {len(comment_list)} 条评论')

                    # 更新cursor
                    cursor = data.get('cursor', cursor + per_page)

                    # 检查是否还有更多
                    if not data.get('has_more', True):
                        log.info('已获取全部评论')
                        break
                else:
                    log.warning(f'第 {page + 1} 页评论数据为空')
                    # 可能需要签名参数
                    break

            except Exception as e:
                log.error(f'评论采集异常: {e}')
                break

            time.sleep(random.uniform(1, 2))

        return comments

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
        posts = []
        max_cursor = 0

        # 解析sec_user_id
        sec_user_id = ParserUtil.extract_sec_user_id(user_url)
        if not sec_user_id:
            log.error(f'无法解析用户ID: {user_url}')
            return []

        log.info(f'用户sec_user_id: {sec_user_id}')

        for page in range(page_count):
            if not self.is_running:
                break

            params = self._get_common_params()
            params.update({
                'sec_user_id': sec_user_id,
                'max_cursor': max_cursor,
                'count': per_page,
            })

            log.info(f'采集第 {page + 1} 页作品')

            try:
                data = self.request.get(self.USER_POST_API, params=params)

                if data and 'aweme_list' in data:
                    post_list = self.parse_post_data(data, page + 1)
                    posts.extend(post_list)
                    log.info(f'第 {page + 1} 页获取 {len(post_list)} 个作品')

                    # 更新cursor
                    max_cursor = data.get('max_cursor', 0)

                    # 检查是否还有更多
                    if not data.get('has_more', True):
                        log.info('已获取全部作品')
                        break
                else:
                    log.warning(f'第 {page + 1} 页作品数据为空')
                    break

            except Exception as e:
                log.error(f'作品采集异常: {e}')
                break

            time.sleep(random.uniform(1, 2))

        return posts

    def parse_search_result(self, data):
        """解析搜索结果"""
        videos = []

        if 'data' not in data:
            return videos

        for item in data.get('data', []):
            if item.get('type') != 'video':
                continue

            aweme_info = item.get('aweme_info', {})
            if not aweme_info:
                continue

            video = {
                'video_id': aweme_info.get('aweme_id', ''),
                'video_title': aweme_info.get('desc', ''),
                'video_link': f"https://www.douyin.com/video/{aweme_info.get('aweme_id', '')}",
                'author_name': aweme_info.get('author', {}).get('nickname', ''),
                'author_id': aweme_info.get('author', {}).get('unique_id', ''),
                'author_uid': aweme_info.get('author', {}).get('sec_uid', ''),
                'author_link': f"https://www.douyin.com/user/{aweme_info.get('author', {}).get('sec_uid', '')}",
                'author_fans': aweme_info.get('author', {}).get('follower_count', 0),
                'publish_time': ParserUtil.format_timestamp(aweme_info.get('create_time', 0)),
                'like_count': aweme_info.get('statistics', {}).get('digg_count', 0),
                'comment_count': aweme_info.get('statistics', {}).get('comment_count', 0),
                'collect_count': aweme_info.get('statistics', {}).get('collect_count', 0),
                'share_count': aweme_info.get('statistics', {}).get('share_count', 0),
            }
            videos.append(video)

        return videos

    def parse_comment_data(self, data, video_id=''):
        """解析评论数据"""
        comments = []

        comment_list = data.get('comments', [])
        aweme_info = data.get('aweme_info', {})

        video_title = aweme_info.get('desc', '') if aweme_info else ''
        video_link = f"https://www.douyin.com/video/{video_id}" if video_id else ''

        for comment in comment_list:
            comment_data = {
                'video_id': video_id,
                'video_title': video_title,
                'video_link': video_link,
                'author_name': comment.get('user', {}).get('nickname', ''),
                'author_id': comment.get('user', {}).get('unique_id', ''),
                'author_uid': comment.get('user', {}).get('sec_uid', ''),
                'author_link': f"https://www.douyin.com/user/{comment.get('user', {}).get('sec_uid', '')}",
                'comment_time': ParserUtil.format_timestamp(comment.get('create_time', 0)),
                'comment_ip': comment.get('ip_label', ''),
                'comment_like': comment.get('digg_count', 0),
                'comment_level': '一级评论',
                'comment_text': comment.get('text', ''),
            }
            comments.append(comment_data)

            # 处理二级评论（回复）
            sub_comments = comment.get('sub_comments', [])
            for sub in sub_comments:
                sub_data = {
                    'video_id': video_id,
                    'video_title': video_title,
                    'video_link': video_link,
                    'author_name': sub.get('user', {}).get('nickname', ''),
                    'author_id': sub.get('user', {}).get('unique_id', ''),
                    'author_uid': sub.get('user', {}).get('sec_uid', ''),
                    'author_link': f"https://www.douyin.com/user/{sub.get('user', {}).get('sec_uid', '')}",
                    'comment_time': ParserUtil.format_timestamp(sub.get('create_time', 0)),
                    'comment_ip': sub.get('ip_label', ''),
                    'comment_like': sub.get('digg_count', 0),
                    'comment_level': '二级评论',
                    'comment_text': sub.get('text', ''),
                }
                comments.append(sub_data)

        return comments

    def parse_post_data(self, data, page=1):
        """解析作品数据"""
        posts = []

        aweme_list = data.get('aweme_list', [])

        # 获取用户信息
        user_info = data.get('user', {})
        author_name = user_info.get('nickname', '')
        author_uid = user_info.get('sec_uid', '')
        author_link = f"https://www.douyin.com/user/{author_uid}"
        author_fans = user_info.get('follower_count', 0)

        for aweme in aweme_list:
            post = {
                'page': page,
                'author_name': author_name,
                'author_uid': author_uid,
                'author_link': author_link,
                'author_fans': author_fans,
                'video_title': aweme.get('desc', ''),
                'video_tags': ','.join(ParserUtil.parse_tags(aweme.get('desc', ''))),
                'video_link': f"https://www.douyin.com/video/{aweme.get('aweme_id', '')}",
                'video_id': aweme.get('aweme_id', ''),
                'publish_time': ParserUtil.format_timestamp(aweme.get('create_time', 0)),
                'video_duration': aweme.get('video', {}).get('duration', 0) // 1000,  # 毫秒转秒
                'is_pinned': aweme.get('is_pinned', False),
                'like_count': aweme.get('statistics', {}).get('digg_count', 0),
                'comment_count': aweme.get('statistics', {}).get('comment_count', 0),
                'collect_count': aweme.get('statistics', {}).get('collect_count', 0),
                'share_count': aweme.get('statistics', {}).get('share_count', 0),
            }
            posts.append(post)

        return posts