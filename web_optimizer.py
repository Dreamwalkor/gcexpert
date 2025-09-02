#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC日志分析Web服务 - 大文件优化版本
专门针对6G大文件处理进行优化
"""

import os
import sys
import asyncio
import json
import tempfile
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from utils.log_loader import LogLoader, GCLogType
from analyzer.metrics import analyze_gc_metrics
from analyzer.jvm_info_extractor import JVMInfoExtractor
from analyzer.pause_distribution_analyzer import PauseDistributionAnalyzer
from parser.g1_parser import parse_gc_log as parse_g1_log
from parser.ibm_parser import parse_gc_log as parse_j9_log
from rules.alert_engine import GCAlertEngine

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置常量
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024  # 10GB
CHUNK_SIZE = 16 * 1024 * 1024  # 16MB chunks for optimal performance
SAMPLE_SIZE = 10000  # 采样事件数量
UPLOAD_DIR = "uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)


class LargeFileOptimizer:
    """大文件处理优化器 - 专门处理6G级别的GC日志"""
    
    def __init__(self):
        self.loader = LogLoader()
        self.alert_engine = GCAlertEngine()
        self.jvm_extractor = JVMInfoExtractor()
        self.pause_analyzer = PauseDistributionAnalyzer()
        
    async def process_large_gc_log(self, file_path: str, progress_callback=None) -> Dict[str, Any]:
        """
        优化的大文件处理流程
        采用分块读取、流式解析、智能采样等技术
        """
        logger.info(f"开始优化处理大文件: {file_path}")
        
        file_size = os.path.getsize(file_path)
        logger.info(f"文件大小: {file_size / (1024**3):.2f} GB")
        
        # 进度回调辅助函数
        def update_progress(stage: str, progress: int, message: str = ""):
            if progress_callback:
                progress_callback(stage, progress, message)
        
        # 1. 快速类型检测 (0-5%)
        update_progress("类型检测", 2, "检测日志格式...")
        log_type = await self._detect_type_fast(file_path)
        logger.info(f"检测到日志类型: {log_type.value}")
        update_progress("类型检测", 5, f"检测到 {log_type.value} 格式")
        
        # 2. 提取JVM环境信息 (5-10%)
        update_progress("环境信息", 7, "提取JVM环境信息...")
        jvm_info = await self._extract_jvm_info(file_path)
        logger.info(f"JVM信息: {jvm_info.get('jvm_version', 'Unknown')}, {jvm_info.get('gc_strategy', 'Unknown')}")
        update_progress("环境信息", 10, "JVM环境信息提取完成")
        
        # 3. 分块流式处理 (10-65%) - 这是最耗时的部分
        update_progress("解析日志", 12, "开始解析GC事件...")
        events = await self._stream_parse_file(file_path, log_type, progress_callback)
        logger.info(f"解析完成，总事件数: {len(events)}")
        
        # 更新JVM信息中的运行时数据 (65-70%)
        update_progress("运行时信息", 67, "更新运行时信息...")
        if events:
            runtime_info = self.jvm_extractor.extract_jvm_info("", events)
            # 只更新运行时相关字段，避免覆盖已正确提取的环境信息
            jvm_info.update({
                'runtime_duration_seconds': runtime_info.get('runtime_duration_seconds', 0),
                'gc_log_start_time': runtime_info.get('gc_log_start_time'),
                'gc_log_end_time': runtime_info.get('gc_log_end_time'),
                'total_gc_events': runtime_info.get('total_gc_events', 0)
            })
        
        # 添加兼容前端的驼峰命名字段 - 只有当值不为None时才添加
        if jvm_info.get("total_memory_mb") is not None:
            jvm_info["totalMemoryMb"] = jvm_info["total_memory_mb"]
        if jvm_info.get("maximum_heap_mb") is not None:
            jvm_info["maximumHeapMb"] = jvm_info["maximum_heap_mb"]
        if jvm_info.get("initial_heap_mb") is not None:
            jvm_info["initialHeapMb"] = jvm_info["initial_heap_mb"]
        if jvm_info.get("runtime_duration_seconds") is not None:
            jvm_info["runtimeDurationSeconds"] = jvm_info["runtime_duration_seconds"]
        
        update_progress("运行时信息", 70, "运行时信息更新完成")
        
        # 4. 智能采样分析 (70-75%)
        update_progress("数据采样", 72, "开始智能采样分析...")
        sampled_events = self._smart_sample(events)
        logger.info(f"采样事件数: {len(sampled_events)}")
        update_progress("数据采样", 75, f"采样完成，分析 {len(sampled_events)} 个关键事件")
        
        # 5. 性能指标分析 (75-82%)
        update_progress("性能分析", 77, "计算性能指标...")
        metrics = analyze_gc_metrics(sampled_events) if sampled_events else None
        update_progress("性能分析", 82, "性能指标计算完成")
        
        # 6. 停顿分布分析 (82-88%)
        update_progress("停顿分析", 84, "分析停顿分布...")
        pause_distribution = self.pause_analyzer.analyze_pause_distribution(sampled_events)
        logger.info(f"停顿分布分析完成，区间数: {len(pause_distribution.get('distribution', []))}")
        update_progress("停顿分析", 88, "停顿分布分析完成")
        
        # 7. 警报检测 (88-93%)
        update_progress("警报检测", 90, "检测性能问题...")
        alerts = self.alert_engine.evaluate_metrics(metrics) if metrics else []
        update_progress("警报检测", 93, f"检测到 {len(alerts)} 个性能警报")
        
        # 8. 生成图表数据 (93-98%)
        update_progress("图表生成", 95, "生成图表数据...")
        chart_data = self._generate_chart_data(sampled_events, events, pause_distribution)
        update_progress("图表生成", 98, "图表数据生成完成")
        
        # 9. 最终整理 (98-100%)
        update_progress("完成处理", 99, "整理分析结果...")
        
        result = {
            "log_type": log_type.value,
            "file_size_gb": file_size / (1024**3),
            "total_events": len(events),
            "analyzed_events": len(sampled_events),
            "jvm_info": jvm_info,
            "metrics": self._serialize_metrics(metrics),
            "pause_distribution": pause_distribution,
            "alerts": [self._serialize_alert(a) for a in alerts],
            "chart_data": chart_data,
            "processing_info": {
                "sampling_ratio": len(sampled_events) / len(events) if events else 0,
                "optimization": "large_file_optimized"
            }
        }
        
        update_progress("完成处理", 100, "分析完成！")
        return result
    
    async def _detect_type_fast(self, file_path: str) -> GCLogType:
        """快速检测日志类型 - 只读取前1MB"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            sample = f.read(1024 * 1024)
        return self.loader.detect_log_type(sample)
    
    async def _extract_jvm_info(self, file_path: str) -> Dict[str, Any]:
        """提取JVM环境信息 - 读取文件开头的环境信息"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # 读取前2MB，通常包含所有初始化信息
                header_content = f.read(2 * 1024 * 1024)
            
            jvm_info = self.jvm_extractor.extract_jvm_info(header_content)
            
            # 不设置默认值，保持None值以便前端判断
            return jvm_info
        except Exception as e:
            logger.warning(f"提取JVM信息失败: {e}")
            return {
                'jvm_version': None,
                'gc_strategy': None,
                'cpu_cores': None,
                'total_memory_mb': None,
                'initial_heap_mb': None,
                'maximum_heap_mb': None,
                'runtime_duration_seconds': None,
                'log_format': 'unknown'
            }
    
    async def _stream_parse_file(self, file_path: str, log_type: GCLogType, progress_callback=None) -> List[Dict]:
        """流式解析大文件"""
        events = []
        total_size = os.path.getsize(file_path)
        processed_size = 0
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            buffer = ""
            chunk_count = 0
            
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    # 处理最后的buffer
                    if buffer:
                        chunk_events = await self._parse_chunk(buffer, log_type)
                        events.extend(chunk_events)
                    break
                
                processed_size += len(chunk.encode('utf-8'))
                chunk_count += 1
                
                # 添加到buffer
                buffer += chunk
                
                # 查找完整的日志行
                if log_type == GCLogType.G1:
                    complete_lines, buffer = self._extract_complete_g1_lines(buffer)
                elif log_type == GCLogType.IBM_J9:
                    complete_lines, buffer = self._extract_complete_j9_entries(buffer)
                else:
                    complete_lines, buffer = buffer, ""
                
                if complete_lines:
                    chunk_events = await self._parse_chunk(complete_lines, log_type)
                    events.extend(chunk_events)
                
                # 更新进度 - 解析阶段占12%-65%的进度，共53%的范围
                file_progress = (processed_size / total_size) * 100
                overall_progress = 12 + int(file_progress * 0.53)  # 12% + 53%的范围
                
                # 每处理一定量数据更新进度
                if chunk_count % 3 == 0:  # 更频繁的进度更新
                    if progress_callback:
                        progress_callback("解析日志", overall_progress, 
                                        f"已处理 {processed_size/(1024**2):.0f}MB / {total_size/(1024**2):.0f}MB，解析到 {len(events)} 个事件")
                    logger.info(f"处理进度: {file_progress:.1f}% ({processed_size/(1024**2):.0f}MB)")
                
                # 允许其他任务执行
                await asyncio.sleep(0.001)
        
        return events
    
    def _extract_complete_g1_lines(self, buffer: str) -> tuple:
        """提取完整的G1日志行"""
        lines = buffer.split('\n')
        complete_lines = '\n'.join(lines[:-1])
        remaining_buffer = lines[-1]
        return complete_lines, remaining_buffer
    
    def _extract_complete_j9_entries(self, buffer: str) -> tuple:
        """提取完整的J9 XML条目"""
        # 查找完整的<gc>...</gc>条目
        entries = []
        remaining = buffer
        
        while True:
            start = remaining.find('<gc ')
            if start == -1:
                break
            
            end = remaining.find('</gc>', start)
            if end == -1:
                remaining = remaining[start:]
                break
            
            entry = remaining[start:end + 5]
            entries.append(entry)
            remaining = remaining[end + 5:]
        
        return '\n'.join(entries), remaining
    
    async def _parse_chunk(self, chunk: str, log_type: GCLogType) -> List[Dict]:
        """解析数据块"""
        try:
            if log_type == GCLogType.G1:
                result = parse_g1_log(chunk)
            elif log_type == GCLogType.IBM_J9:
                result = parse_j9_log(chunk)
            else:
                return []
            
            return result.get('events', [])
        except Exception as e:
            logger.warning(f"解析块失败: {e}")
            return []
    
    def _smart_sample(self, events: List[Dict]) -> List[Dict]:
        """智能采样 - 保留关键事件和均匀分布"""
        if len(events) <= SAMPLE_SIZE:
            return events
        
        # 分离关键事件（如Full GC）
        critical_events = []
        normal_events = []
        
        for event in events:
            gc_type = event.get('gc_type', '').lower()
            pause_time = event.get('pause_time', 0)
            
            # 关键事件：Full GC或长停顿
            if 'full' in gc_type or pause_time > 100:
                critical_events.append(event)
            else:
                normal_events.append(event)
        
        # 保留所有关键事件
        sampled = critical_events[:]
        
        # 从普通事件中均匀采样
        remaining_slots = SAMPLE_SIZE - len(critical_events)
        if remaining_slots > 0 and normal_events:
            step = max(1, len(normal_events) // remaining_slots)
            sampled.extend(normal_events[::step][:remaining_slots])
        
        # 按时间排序
        sampled.sort(key=lambda x: x.get('timestamp', 0))
        
        logger.info(f"智能采样: 关键事件 {len(critical_events)}, 普通事件采样 {len(sampled) - len(critical_events)}")
        return sampled
    
    def _generate_chart_data(self, sampled_events: List[Dict], all_events: List[Dict], pause_distribution: Optional[Dict] = None) -> Dict[str, Any]:
        """生成优化的图表数据"""
        # 进一步采样用于图表显示（最多1000个点）
        chart_events = sampled_events[::max(1, len(sampled_events) // 1000)][:1000]
        
        # 时间序列数据 - 增强版本，包含更多内存区域信息
        timeline_data = []
        for i, event in enumerate(chart_events):
            # 获取基本内存信息 - 兼容G1和J9格式
            heap_before = event.get('heap_before', 0)
            heap_after = event.get('heap_after', 0)
            heap_total = event.get('heap_total', 0)
            
            # 处理内存单位（字节转MB）
            # 检查是否为字节单位（通常大于1MB）
            if heap_before > 1048576:  # 如果大于1MB，假设是字节单位
                heap_before = heap_before / (1024 * 1024)  # 转换为MB
                heap_after = heap_after / (1024 * 1024) if heap_after else 0
                heap_total = heap_total / (1024 * 1024) if heap_total else 0
            gc_type = event.get('gc_type', 'unknown')
            
            # 获取停顿时间 - 兼容不同字段名
            pause_time = event.get('pause_time') or event.get('duration', 0)
            
            # 处理IBM J9VM特有的内存区域信息
            nursery_before = event.get('nursery_before', 0)
            nursery_after = event.get('nursery_after', 0)
            tenure_before = event.get('tenure_before', 0)
            tenure_after = event.get('tenure_after', 0)
            
            # 处理内存区域单位（字节转MB）
            if nursery_before and nursery_before > 1048576:  # 如果大于1MB，假设是字节单位
                nursery_before = nursery_before / (1024 * 1024)
                nursery_after = nursery_after / (1024 * 1024) if nursery_after else 0
                tenure_before = tenure_before / (1024 * 1024) if tenure_before else 0
                tenure_after = tenure_after / (1024 * 1024) if tenure_after else 0
            
            # 处理时间戳 - 转换为格式化时间字符串，去掉时区信息
            timestamp = event.get('timestamp', i)
            if isinstance(timestamp, str) and 'T' in timestamp:
                # 如果已经是格式化时间字符串，去掉时区信息
                # 例如：2025-08-26T15:04:37.088+0800 -> 2025-08-26T15:04:37.088
                if '+' in timestamp:
                    formatted_timestamp = timestamp.split('+')[0]
                elif '-' in timestamp and timestamp.count('-') > 2:  # 确保不是日期中的-
                    # 处理负时区偏移，例如 2025-08-26T15:04:37.088-0500
                    last_dash = timestamp.rfind('-')
                    if last_dash > 10:  # 确保不是日期部分的-
                        formatted_timestamp = timestamp[:last_dash]
                    else:
                        formatted_timestamp = timestamp
                else:
                    formatted_timestamp = timestamp
            else:
                # 如果是数字或其他格式，转换为时间格式
                # 假设是从某个基准时间开始的秒数或事件序号
                from datetime import datetime, timedelta
                base_time = datetime(2025, 8, 26, 15, 4, 37, 88000)  # 2025-08-26T15:04:37.088
                if isinstance(timestamp, (int, float)):
                    # 如果是数字，假设是秒数偏移
                    event_time = base_time + timedelta(seconds=timestamp * 10)  # 每10秒一个事件
                else:
                    # 如果是其他格式，使用事件索引
                    event_time = base_time + timedelta(seconds=i * 10)
                formatted_timestamp = event_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]  # 毫秒精度
            
            # 根据GC类型估算Eden、Survivor、Old区使用情况
            # 对于IBM J9VM，优先使用真实的内存区域数据
            if nursery_before is not None and nursery_after is not None:
                # J9VM的Nursery区类似于G1的Eden区
                estimated_eden_before = nursery_before
                estimated_eden_after = nursery_after
                estimated_old_before = tenure_before if tenure_before else heap_before * 0.7
                estimated_old_after = tenure_after if tenure_after else heap_after * 0.8
                # 处理Survivor区域
                survivor_before = event.get('survivor_before')
                if survivor_before and survivor_before > 1048576:  # 字节转MB
                    survivor_before = survivor_before / (1024 * 1024)
                estimated_survivor = survivor_before if survivor_before else heap_before * 0.05
            elif gc_type == 'young' or gc_type == 'scavenge':
                # Young GC/Scavenge主要回收Eden区
                estimated_eden_before = heap_before * 0.3  # 30%估算为Eden区
                estimated_eden_after = heap_after * 0.1    # GC后Eden区几乎为空
                estimated_survivor = heap_before * 0.05    # 5%估算为Survivor区
                estimated_old_before = heap_before * 0.65   # 65%估算为老年代
                estimated_old_after = heap_after * 0.8     # GC后老年代略有增加
            elif gc_type == 'mixed' or gc_type == 'global':
                # Mixed GC/Global GC同时回收新生代和部分老年代
                estimated_eden_before = heap_before * 0.25
                estimated_eden_after = heap_after * 0.05
                estimated_survivor = heap_before * 0.08
                estimated_old_before = heap_before * 0.67
                estimated_old_after = heap_after * 0.75
            else:  # full GC 或 concurrent GC
                # Full GC回收所有区域
                estimated_eden_before = heap_before * 0.2
                estimated_eden_after = 0  # Full GC后Eden区为空
                estimated_survivor = heap_before * 0.05
                estimated_old_before = heap_before * 0.75
                estimated_old_after = heap_after * 0.9
            
            # 处理Metaspace单位转换（KB转MB）
            metaspace_before = event.get('metaspace_before')
            metaspace_after = event.get('metaspace_after')
            metaspace_total = event.get('metaspace_total')
            
            if metaspace_before:
                metaspace_before = metaspace_before / 1024.0  # KB转MB
            if metaspace_after:
                metaspace_after = metaspace_after / 1024.0
            if metaspace_total:
                metaspace_total = metaspace_total / 1024.0
            
            data_point = {
                "index": i,
                "event_id": event.get('event_id', i),
                "timestamp": formatted_timestamp,  # 使用格式化的时间字符串
                "original_timestamp": event.get('timestamp', i),  # 保留原始时间戳
                "pause_time": pause_time,  # 兼容G1和J9的字段名
                "gc_type": gc_type,
                # 堆内存信息
                "heap_before_mb": heap_before,
                "heap_after_mb": heap_after,
                "heap_total_mb": heap_total,
                "heap_utilization": (heap_before / max(heap_total, 1)) * 100 if heap_total > 0 else 0,
                # 估算的内存区域信息
                "eden_before_mb": estimated_eden_before,
                "eden_after_mb": estimated_eden_after,
                "survivor_before_mb": estimated_survivor,
                "survivor_after_mb": estimated_survivor * 0.7,  # 估算survivor也有部分回收
                "old_before_mb": estimated_old_before,
                "old_after_mb": estimated_old_after,
                # Metaspace信息（优先使用解析得到的真实数据）
                "metaspace_before_mb": metaspace_before if metaspace_before else heap_total * 0.05,  # KB转MB或估算
                "metaspace_after_mb": metaspace_after if metaspace_after else heap_total * 0.05,   # KB转MB或估算
                "metaspace_total_mb": metaspace_total if metaspace_total else heap_total * 0.08,   # KB转MB或估算
                # 计算回收效率
                "memory_reclaimed_mb": heap_before - heap_after,
                "reclaim_efficiency": ((heap_before - heap_after) / max(heap_before, 1)) * 100 if heap_before > 0 else 0
            }
            timeline_data.append(data_point)
        
        # GC类型统计
        gc_stats = {}
        for event in sampled_events:
            gc_type = event.get('gc_type', 'unknown')
            gc_stats[gc_type] = gc_stats.get(gc_type, 0) + 1
        
        # 停顿时间分布 - 兼容G1和J9格式
        pause_times = []
        for e in sampled_events:
            pause_time = e.get('pause_time') or e.get('duration', 0)
            pause_times.append(pause_time)
        pause_histogram = self._create_histogram(pause_times, 20)
        
        # 内存使用分布
        heap_utilizations = []
        memory_reclaim_rates = []
        for event in timeline_data:
            heap_utilizations.append(event['heap_utilization'])
            memory_reclaim_rates.append(event['reclaim_efficiency'])
        
        heap_utilization_histogram = self._create_histogram(heap_utilizations, 15) if heap_utilizations else {"bin_edges": [], "counts": []}
        reclaim_rate_histogram = self._create_histogram(memory_reclaim_rates, 15) if memory_reclaim_rates else {"bin_edges": [], "counts": []}
        
        return {
            "timeline": timeline_data,
            "gc_type_stats": gc_stats,
            "pause_histogram": pause_histogram,
            "pause_distribution": pause_distribution,  # 新增：停顿分布分析结果
            "heap_utilization_histogram": heap_utilization_histogram,
            "reclaim_rate_histogram": reclaim_rate_histogram,
            "summary": {
                "total_events": len(all_events),
                "chart_events": len(chart_events),
                "avg_pause": sum(pause_times) / len(pause_times) if pause_times else 0,
                "max_pause": max(pause_times) if pause_times else 0,
                "avg_heap_utilization": sum(heap_utilizations) / len(heap_utilizations) if heap_utilizations else 0,
                "avg_reclaim_rate": sum(memory_reclaim_rates) / len(memory_reclaim_rates) if memory_reclaim_rates else 0
            }
        }
    
    def _create_histogram(self, values: List[float], bins: int) -> Dict[str, List]:
        """创建直方图数据"""
        if not values:
            return {"bins": [], "counts": []}
        
        min_val, max_val = min(values), max(values)
        bin_width = (max_val - min_val) / bins if max_val > min_val else 1
        
        bin_edges = [min_val + i * bin_width for i in range(bins + 1)]
        counts = [0] * bins
        
        for val in values:
            bin_idx = min(int((val - min_val) / bin_width), bins - 1)
            counts[bin_idx] += 1
        
        return {
            "bin_edges": bin_edges,
            "counts": counts
        }
    
    def _serialize_metrics(self, metrics: Any) -> Dict[str, Any]:
        """序列化metrics对象"""
        if not metrics:
            return {}
        
        return {
            "throughput_percentage": getattr(metrics, 'throughput_percentage', 0),
            "avg_pause_time": getattr(metrics, 'avg_pause_time', 0),
            "max_pause_time": getattr(metrics, 'max_pause_time', 0),
            "p99_pause_time": getattr(metrics, 'p99_pause_time', 0),
            "gc_frequency": getattr(metrics, 'gc_frequency', 0),
            "performance_score": getattr(metrics, 'performance_score', 0),
            "health_status": getattr(metrics, 'health_status', 'unknown')
        }
    
    def _serialize_alert(self, alert: Any) -> Dict[str, Any]:
        """序列化alert对象"""
        return {
            "severity": alert.severity.value,
            "category": alert.category.value,
            "message": alert.message,
            "recommendation": alert.recommendation
        }


# 测试函数
async def test_large_file_processing(test_file_path=None):
    """测试大文件处理功能"""
    optimizer = LargeFileOptimizer()
    
    # 确定测试文件
    if test_file_path and os.path.exists(test_file_path):
        test_file = test_file_path
    elif os.path.exists("test/data/sample_g1.log"):
        test_file = "test/data/sample_g1.log"
    else:
        print("⚠️ 测试文件不存在")
        return
    
    print(f"🧪 测试文件: {test_file}")
    file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
    print(f"📁 文件大小: {file_size_mb:.1f} MB")
    
    # 记录开始时间
    import time
    start_time = time.time()
    
    result = await optimizer.process_large_gc_log(test_file)
    
    # 记录结束时间
    end_time = time.time()
    processing_time = end_time - start_time
    
    print(f"✅ 处理完成 (耗时: {processing_time:.2f}秒):")
    print(f"   日志类型: {result['log_type']}")
    print(f"   总事件数: {result['total_events']:,}")
    print(f"   分析事件数: {result['analyzed_events']:,}")
    print(f"   采样比例: {result['processing_info']['sampling_ratio']:.2%}")
    print(f"   处理速度: {file_size_mb/processing_time:.1f} MB/秒")
    
    if result['metrics']:
        metrics = result['metrics']
        print(f"   性能评分: {metrics.get('performance_score', 0):.1f}/100")
        print(f"   平均停顿: {metrics.get('avg_pause_time', 0):.1f}ms")
        print(f"   最大停顿: {metrics.get('max_pause_time', 0):.1f}ms")
    
    print(f"   警报数量: {len(result['alerts'])}")
    
    # 显示一些警报示例
    if result['alerts']:
        print(f"\n⚠️ 警报示例:")
        for i, alert in enumerate(result['alerts'][:3]):
            print(f"   {i+1}. [{alert['severity']}] {alert['message']}")


if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(test_large_file_processing(test_file))