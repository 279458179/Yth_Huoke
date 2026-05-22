"""数据解析工具"""
import re
from urllib.parse import urlparse, parse_qs


class ParserUtil:
    """数据解析工具类"""

    @staticmethod
    def extract_video_id(url):
        """
        从抖音视频链接中提取视频ID

        支持格式:
        - https://www.douyin.com/video/123456789
        - https://v.douyin.com/xxx/ (短链接)
        """
        # PC端链接
        match = re.search(r'/video/(\d+)', url)
        if match:
            return match.group(1)

        # 移动端分享链接格式
        match = re.search(r'modal_id=(\d+)', url)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def extract_sec_user_id(url):
        """
        从抖音用户主页链接中提取sec_user_id

        支持格式:
        - https://www.douyin.com/user/MS4wLjABAAAAxxx
        """
        match = re.search(r'/user/([A-Za-z0-9_-]+)', url)
        if match:
            return match.group(1)

        return None

    @staticmethod
    def extract_douyin_id(url):
        """
        从抖音主页链接中提取抖音号
        """
        # 从URL参数中提取
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'dy_id' in params:
            return params['dy_id'][0]

        return None

    @staticmethod
    def format_timestamp(timestamp):
        """
        格式化时间戳

        Args:
            timestamp: Unix时间戳（秒或毫秒）
        Returns:
            格式化的时间字符串
        """
        if timestamp is None:
            return ''

        # 处理毫秒时间戳
        if timestamp > 10000000000:
            timestamp = timestamp / 1000

        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return str(timestamp)

    @staticmethod
    def format_number(num):
        """
        格式化数字（处理大数字显示）
        """
        if num is None:
            return 0

        if isinstance(num, str):
            try:
                num = int(num)
            except:
                return num

        if num >= 10000:
            return f'{num/10000:.1f}w'
        elif num >= 1000:
            return f'{num/1000:.1f}k'
        return num

    @staticmethod
    def clean_text(text):
        """清理文本内容"""
        if not text:
            return ''

        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    @staticmethod
    def parse_tags(text):
        """解析视频标签/话题"""
        if not text:
            return []

        # 匹配 #话题# 格式
        tags = re.findall(r'#([^#\s]+)#', text)
        return tags

    @staticmethod
    def is_video_url(text):
        """判断是否是视频链接"""
        patterns = [
            r'douyin\.com/video/',
            r'v\.douyin\.com',
            r'modal_id=\d+',
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    @staticmethod
    def is_user_url(text):
        """判断是否是用户主页链接"""
        patterns = [
            r'douyin\.com/user/',
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False