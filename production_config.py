#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生产环境配置文件
针对6G大文件处理优化的生产环境设置
"""

import os
from typing import Dict, Any

class ProductionConfig:
    """生产环境配置类"""
    
    # 服务器配置
    HOST = "0.0.0.0"
    PORT = 8000
    WORKERS = 4  # 建议设置为CPU核心数
    
    # 文件处理配置
    MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
    UPLOAD_DIR = "/data/gc_uploads"  # 生产环境建议使用独立磁盘
    CHUNK_SIZE = 32 * 1024 * 1024    # 32MB chunks for better performance
    SAMPLE_SIZE = 50000              # 增加采样数量以提高分析精度
    
    # 内存优化配置
    MAX_MEMORY_USAGE = 4 * 1024 * 1024 * 1024  # 4GB内存限制
    ENABLE_MEMORY_MONITOR = True
    
    # 并发控制
    MAX_CONCURRENT_UPLOADS = 10
    MAX_CONCURRENT_PROCESSING = 3
    PROCESSING_TIMEOUT = 1800  # 30分钟超时
    
    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FILE = "/var/log/gc_analyzer.log"
    LOG_ROTATION = "100MB"
    
    # 缓存配置
    ENABLE_RESULT_CACHE = True
    CACHE_TTL = 3600  # 1小时
    CACHE_DIR = "/tmp/gc_cache"
    
    # 安全配置
    ENABLE_RATE_LIMITING = True
    RATE_LIMIT = "100/hour"  # 每小时100次请求
    ALLOWED_ORIGINS = ["*"]  # 生产环境应限制为特定域名
    
    # 性能监控
    ENABLE_METRICS = True
    METRICS_ENDPOINT = "/metrics"
    
    @classmethod
    def get_uvicorn_config(cls) -> Dict[str, Any]:
        """获取Uvicorn服务器配置"""
        return {
            "host": cls.HOST,
            "port": cls.PORT,
            "workers": cls.WORKERS,
            "log_level": cls.LOG_LEVEL.lower(),
            "access_log": True,
            "loop": "uvloop",
            "http": "httptools"
        }
    
    @classmethod
    def setup_directories(cls):
        """创建必要的目录"""
        directories = [
            cls.UPLOAD_DIR,
            cls.CACHE_DIR,
            os.path.dirname(cls.LOG_FILE)
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ 目录已创建: {directory}")


class DevelopmentConfig(ProductionConfig):
    """开发环境配置"""
    
    HOST = "127.0.0.1"
    PORT = 8000
    WORKERS = 1
    LOG_LEVEL = "DEBUG"
    ENABLE_RATE_LIMITING = False
    MAX_CONCURRENT_UPLOADS = 3
    MAX_CONCURRENT_PROCESSING = 1


# 环境配置选择
def get_config():
    """根据环境变量选择配置"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionConfig()
    else:
        return DevelopmentConfig()


if __name__ == "__main__":
    # 测试配置
    config = get_config()
    print(f"🔧 当前环境: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"📡 服务器配置: {config.HOST}:{config.PORT}")
    print(f"👥 工作进程数: {config.WORKERS}")
    print(f"📁 上传目录: {config.UPLOAD_DIR}")
    print(f"💾 最大文件大小: {config.MAX_FILE_SIZE / (1024**3):.1f}GB")
    print(f"🚀 块大小: {config.CHUNK_SIZE / (1024**2):.0f}MB")
    print(f"📊 采样大小: {config.SAMPLE_SIZE:,}")
    
    # 创建目录
    config.setup_directories()