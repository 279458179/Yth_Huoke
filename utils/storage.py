"""数据存储模块"""
import os
import json
import csv
import time
from datetime import datetime


class StorageUtil:
    """数据存储工具类"""

    def __init__(self, output_dir=None):
        if output_dir is None:
            # 默认存储在 results 目录
            base_dir = os.path.dirname(os.path.dirname(__file__))
            output_dir = os.path.join(base_dir, 'results')

        self.csv_dir = os.path.join(output_dir, 'csv')
        self.json_dir = os.path.join(output_dir, 'json')

        # 创建目录
        os.makedirs(self.csv_dir, exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)

    def save_csv(self, data, filename, fields=None):
        """
        保存数据到CSV文件

        Args:
            data: 数据列表（字典列表）
            filename: 文件名（不含扩展名）
            fields: 字段列表，如果为None则使用数据的keys
        """
        if not data:
            return

        filepath = os.path.join(self.csv_dir, f'{filename}.csv')

        # 获取字段
        if fields is None:
            fields = list(data[0].keys())

        # 判断是否需要写表头
        header = not os.path.exists(filepath)

        with open(filepath, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            if header:
                writer.writeheader()
            writer.writerows(data)

        return filepath

    def save_json(self, data, filename):
        """
        保存数据到JSON文件

        Args:
            data: 数据（字典或列表）
            filename: 文件名（不含扩展名）
        """
        filepath = os.path.join(self.json_dir, f'{filename}.json')

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return filepath

    def append_json(self, data, filename):
        """
        追加数据到JSON文件（用于增量采集）
        """
        filepath = os.path.join(self.json_dir, f'{filename}.json')

        # 如果文件存在，读取现有数据
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if isinstance(existing, list):
                    data = existing + data
                elif isinstance(existing, dict):
                    data = {**existing, **data}

        return self.save_json(data, filename)

    def get_timestamp_filename(self, prefix):
        """生成带时间戳的文件名"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f'{prefix}_{timestamp}'