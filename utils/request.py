"""HTTP请求封装模块"""
import time
import random
import requests
from .logger import log


class RequestUtil:
    """HTTP请求工具类"""

    # 默认请求头
    DEFAULT_HEADERS = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Connection': 'keep-alive',
    }

    # 随机User-Agent池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]

    def __init__(self, cookie=None, referer=None):
        self.session = requests.Session()
        self.cookie = cookie
        self.referer = referer

        # 设置默认请求头
        self.headers = self.DEFAULT_HEADERS.copy()
        self.headers['User-Agent'] = random.choice(self.USER_AGENTS)

        if cookie:
            self.headers['Cookie'] = cookie
        if referer:
            self.headers['Referer'] = referer

    def set_cookie(self, cookie):
        """设置Cookie"""
        self.cookie = cookie
        self.headers['Cookie'] = cookie

    def set_referer(self, referer):
        """设置Referer"""
        self.referer = referer
        self.headers['Referer'] = referer

    def get(self, url, params=None, headers=None, retry=3, delay=1):
        """
        发送GET请求

        Args:
            url: 请求URL
            params: 请求参数
            headers: 额外请求头
            retry: 重试次数
            delay: 请求间隔（秒）
        Returns:
            响应数据（JSON）
        """
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)

        for attempt in range(retry):
            try:
                # 请求间隔
                if attempt > 0:
                    time.sleep(delay * (attempt + 1))

                response = self.session.get(
                    url,
                    params=params,
                    headers=req_headers,
                    timeout=30
                )

                if response.status_code == 200:
                    # 随机延时，模拟人类行为
                    time.sleep(delay + random.random())
                    return response.json()
                else:
                    log.warning(f'请求失败，状态码: {response.status_code}')

            except requests.exceptions.RequestException as e:
                log.error(f'请求异常: {e}')
                if attempt == retry - 1:
                    raise

        return None

    def post(self, url, data=None, json=None, headers=None, retry=3, delay=1):
        """
        发送POST请求
        """
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)

        for attempt in range(retry):
            try:
                if attempt > 0:
                    time.sleep(delay * (attempt + 1))

                response = self.session.post(
                    url,
                    data=data,
                    json=json,
                    headers=req_headers,
                    timeout=30
                )

                if response.status_code == 200:
                    time.sleep(delay + random.random())
                    return response.json()
                else:
                    log.warning(f'请求失败，状态码: {response.status_code}')

            except requests.exceptions.RequestException as e:
                log.error(f'请求异常: {e}')
                if attempt == retry - 1:
                    raise

        return None

    def close(self):
        """关闭Session"""
        self.session.close()