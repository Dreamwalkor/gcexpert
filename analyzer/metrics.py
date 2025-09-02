#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC性能指标分析器
提供吞吐量、延迟、内存使用等关键性能指标的计算和分析
"""

import statistics
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from collections import defaultdict
import math
import numpy as np


@dataclass
class GCMetrics:
    """GC性能指标数据结构"""
    # 吞吐量指标
    throughput_percentage: float  # 应用吞吐量百分比
    gc_overhead_percentage: float  # GC开销百分比
    
    # 延迟指标
    avg_pause_time: float  # 平均停顿时间(ms)
    p50_pause_time: float  # P50停顿时间(ms)
    p90_pause_time: float  # P90停顿时间(ms)
    p95_pause_time: float  # P95停顿时间(ms)
    p99_pause_time: float  # P99停顿时间(ms)
    max_pause_time: float  # 最大停顿时间(ms)
    min_pause_time: float  # 最小停顿时间(ms)
    
    # 频率指标
    gc_frequency: float  # GC频率(次/秒)
    young_gc_frequency: float  # Young GC频率
    full_gc_frequency: float  # Full GC频率
    
    # 内存指标
    avg_heap_utilization: float  # 平均堆利用率
    max_heap_utilization: float  # 最大堆利用率
    memory_allocation_rate: float  # 内存分配率(MB/秒)
    memory_reclaim_efficiency: float  # 内存回收效率
    
    # 趋势指标
    pause_time_trend: str  # 停顿时间趋势: 'stable', 'increasing', 'decreasing'
    memory_usage_trend: str  # 内存使用趋势
    
    # 总体评估
    performance_score: float  # 性能评分(0-100)
    health_status: str  # 健康状态: 'excellent', 'good', 'warning', 'critical'


class GCMetricsAnalyzer:
    """GC性能指标分析器"""
    
    def __init__(self):
        self.thresholds = {
            'excellent_throughput': 0.98,  # 98%以上吞吐量为优秀
            'good_throughput': 0.95,       # 95%以上吞吐量为良好
            'warning_pause_time': 100,     # 100ms以上停顿为警告
            'critical_pause_time': 500,    # 500ms以上停顿为严重
            'high_gc_frequency': 10,       # 10次/秒以上为高频
        }
    
    def analyze(self, events: List[Dict], time_window: Optional[float] = None) -> GCMetrics:
        """
        分析GC事件并生成性能指标
        
        Args:
            events: GC事件列表
            time_window: 分析时间窗口(秒)，如果为None则分析整个时间段
            
        Returns:
            GC性能指标对象
        """
        if not events:
            return self._empty_metrics()
        
        # 计算时间窗口
        if time_window is None:
            time_window = self._calculate_time_window(events)
        
        # 计算各项指标
        throughput_metrics = self._calculate_throughput(events, time_window)
        latency_metrics = self._calculate_latency_metrics(events)
        frequency_metrics = self._calculate_frequency_metrics(events, time_window)
        memory_metrics = self._calculate_memory_metrics(events)
        trend_metrics = self._calculate_trend_metrics(events)
        
        # 计算性能评分和健康状态
        performance_score = self._calculate_performance_score(
            throughput_metrics, latency_metrics, frequency_metrics
        )
        health_status = self._determine_health_status(performance_score, latency_metrics)
        
        return GCMetrics(
            # 吞吐量指标
            throughput_percentage=throughput_metrics['throughput'],
            gc_overhead_percentage=throughput_metrics['gc_overhead'],
            
            # 延迟指标
            avg_pause_time=latency_metrics['avg'],
            p50_pause_time=latency_metrics['p50'],
            p90_pause_time=latency_metrics['p90'],
            p95_pause_time=latency_metrics['p95'],
            p99_pause_time=latency_metrics['p99'],
            max_pause_time=latency_metrics['max'],
            min_pause_time=latency_metrics['min'],
            
            # 频率指标
            gc_frequency=frequency_metrics['total'],
            young_gc_frequency=frequency_metrics['young'],
            full_gc_frequency=frequency_metrics['full'],
            
            # 内存指标
            avg_heap_utilization=memory_metrics['avg_utilization'],
            max_heap_utilization=memory_metrics['max_utilization'],
            memory_allocation_rate=memory_metrics['allocation_rate'],
            memory_reclaim_efficiency=memory_metrics['reclaim_efficiency'],
            
            # 趋势指标
            pause_time_trend=trend_metrics['pause_trend'],
            memory_usage_trend=trend_metrics['memory_trend'],
            
            # 总体评估
            performance_score=performance_score,
            health_status=health_status
        )
    
    def _empty_metrics(self) -> GCMetrics:
        """返回空的指标对象"""
        return GCMetrics(
            throughput_percentage=0.0,
            gc_overhead_percentage=0.0,
            avg_pause_time=0.0,
            p50_pause_time=0.0,
            p90_pause_time=0.0,
            p95_pause_time=0.0,
            p99_pause_time=0.0,
            max_pause_time=0.0,
            min_pause_time=0.0,
            gc_frequency=0.0,
            young_gc_frequency=0.0,
            full_gc_frequency=0.0,
            avg_heap_utilization=0.0,
            max_heap_utilization=0.0,
            memory_allocation_rate=0.0,
            memory_reclaim_efficiency=0.0,
            pause_time_trend='stable',
            memory_usage_trend='stable',
            performance_score=0.0,
            health_status='unknown'
        )
    
    def _calculate_time_window(self, events: List[Dict]) -> float:
        """计算事件的时间窗口"""
        if len(events) < 2:
            return 1.0  # 默认1秒
        
        timestamps = []
        for event in events:
            timestamp = event.get('timestamp', 0)
            # 处理字符串时间戳(如J9日志)
            if isinstance(timestamp, str):
                # 尝试从时间戳字符串中提取数值
                try:
                    # 假设格式为 "2024-01-01T10:00:01.123"
                    if 'T' in timestamp:
                        time_part = timestamp.split('T')[1]
                        time_components = time_part.split(':')
                        # 转换为秒数
                        hours = float(time_components[0])
                        minutes = float(time_components[1])
                        seconds = float(time_components[2]) if len(time_components) > 2 else 0
                        timestamp = hours * 3600 + minutes * 60 + seconds
                    else:
                        timestamp = float(timestamp)
                except (ValueError, IndexError):
                    timestamp = len(timestamps)  # 使用索引作为默认时间戳
            timestamps.append(float(timestamp))
        
        if not timestamps or len(set(timestamps)) < 2:
            return 1.0  # 如果所有时间戳相同，返回默认值
        
        return max(timestamps) - min(timestamps)
    
    def _calculate_throughput(self, events: List[Dict], time_window: float) -> Dict[str, float]:
        """计算吞吐量指标"""
        total_gc_time = sum(event.get('pause_time', event.get('duration', 0)) for event in events)
        total_time = time_window * 1000  # 转换为毫秒
        
        if total_time <= 0:
            return {'throughput': 0.0, 'gc_overhead': 0.0}
        
        gc_overhead = min(total_gc_time / total_time, 1.0)  # 限制在100%以内
        throughput = max(1.0 - gc_overhead, 0.0)  # 确保非负
        
        return {
            'throughput': throughput * 100,  # 转换为百分比
            'gc_overhead': gc_overhead * 100
        }
    
    def _calculate_latency_metrics(self, events: List[Dict]) -> Dict[str, float]:
        """计算延迟指标"""
        print("\n[DEBUG] 计算百分位统计开始...")
        pause_times = []
        for event in events:
            # 支持G1日志的pause_time和J9日志的duration
            pause_time = event.get('pause_time', event.get('duration', 0))
            if pause_time > 0:  # 只添加大于0的停顿时间
                pause_times.append(pause_time)
        
        print(f"[DEBUG] 提取的停顿时间数据点数量: {len(pause_times)}")
        if len(pause_times) > 0:
            print(f"[DEBUG] 停顿时间范围: {min(pause_times):.1f}ms - {max(pause_times):.1f}ms")
            if len(pause_times) >= 10:
                print(f"[DEBUG] 停顿时间样本: {pause_times[:5]} ... {pause_times[-5:]}")
        
        # 分析原始数据中0值的比例
        all_pause_times = []
        for event in events:
            # 这里收集所有停顿时间包括0值
            pause_time = event.get('pause_time', event.get('duration', 0))
            all_pause_times.append(pause_time)
            
        zero_count = len([t for t in all_pause_times if t == 0])
        if len(all_pause_times) > 0:
            zero_percentage = (zero_count / len(all_pause_times)) * 100
            print(f"[DEBUG] 停顿时间为0的比例: {zero_percentage:.1f}% ({zero_count}/{len(all_pause_times)})")
            
            if zero_percentage > 95:
                print(f"[DEBUG] 警告: 0值过多，可能导致百分位统计异常")
        
        # 检查是否有足够的数据计算百分位数
        if len(pause_times) < 4:  # 至少需要4个数据点计算P99
            print("[DEBUG] 数据点不足，无法计算百分位数")
            if len(pause_times) > 0:
                # 如果有一些数据，但不足以计算百分位数，则使用均值代替
                avg = statistics.mean(pause_times)
                max_val = max(pause_times)
                min_val = min(pause_times)
                print(f"[DEBUG] 使用最大值作为百分位数估计: {max_val:.1f}ms")
                return {
                    'avg': avg, 
                    'p50': max_val,  # 使用最大值作为估计
                    'p90': max_val, 
                    'p95': max_val,
                    'p99': max_val,
                    'max': max_val, 
                    'min': min_val,
                    'insufficient_data': True  # 标记数据不足
                }
            else:
                # 没有有效数据
                print("[DEBUG] 完全没有有效数据")
                return {
                    'avg': 0.0, 'p50': 0.0, 'p90': 0.0, 'p95': 0.0, 'p99': 0.0,
                    'max': 0.0, 'min': 0.0,
                    'insufficient_data': True  # 标记数据不足
                }
        
        # 高百分位异常检测：在某些情况下，99%的值都很小，只有1%是极端大值，导致P99异常
        is_abnormal_distribution = False
        if len(pause_times) >= 100:  # 至少需要100个点才能分析正确
            sorted_times = sorted(pause_times)
            p95_index = int(len(sorted_times) * 0.95)
            p99_index = int(len(sorted_times) * 0.99)
            
            # 检查P99是否比P95大出过多
            if p99_index < len(sorted_times) and p95_index < len(sorted_times):
                p95_value = sorted_times[p95_index]
                p99_value = sorted_times[p99_index]
                
                if p99_value > p95_value * 10:  # P99比P95大超10倍
                    print(f"[DEBUG] 检测到异常分布: P95={p95_value:.1f}ms, P99={p99_value:.1f}ms, 差距倍数={p99_value/p95_value:.1f}x")
                    is_abnormal_distribution = True
        
        pause_times.sort()
        
        # 使用numpy计算更精确的百分位数
        try:
            percentiles = np.percentile(pause_times, [50, 90, 95, 99])
            p50, p90, p95, p99 = percentiles
            print(f"[DEBUG] 百分位计算结果: P50={p50:.1f}ms, P90={p90:.1f}ms, P95={p95:.1f}ms, P99={p99:.1f}ms")
            
            # 如果是异常分布，考虑处理
            if is_abnormal_distribution and p50 == 0.0 and p90 == 0.0 and p95 == 0.0 and p99 > 0.0:
                print("[DEBUG] 应用异常分布修正: 使用P99值作为其他百分位的参考")
                p_avg = (p99 * 0.5)  # 假设平均值在P99的一半
                p50 = (p99 * 0.3)    # 假设值
                p90 = (p99 * 0.7)    # 假设值
                p95 = (p99 * 0.85)   # 假设值
                print(f"[DEBUG] 修正后的值: P50={p50:.1f}ms, P90={p90:.1f}ms, P95={p95:.1f}ms, P99={p99:.1f}ms")
                
        except (ImportError, Exception) as e:
            # 如果numpy不可用或计算出错，回退到简单实现
            print(f"[DEBUG] 百分位计算警告: {e}")
            p50 = self._percentile(pause_times, 50)
            p90 = self._percentile(pause_times, 90)
            p95 = self._percentile(pause_times, 95)
            p99 = self._percentile(pause_times, 99)
        
        result = {
            'avg': statistics.mean(pause_times),
            'p50': float(p50),
            'p90': float(p90),
            'p95': float(p95),
            'p99': float(p99),
            'max': max(pause_times),
            'min': min(pause_times),
            'insufficient_data': False,  # 数据充足
            'abnormal_distribution': is_abnormal_distribution  # 帮助前端识别异常分布
        }
        print(f"[DEBUG] 返回结果: {result}")
        return result
    
    def _calculate_frequency_metrics(self, events: List[Dict], time_window: float) -> Dict[str, float]:
        """计算GC频率指标"""
        if time_window <= 0:
            return {'total': 0.0, 'young': 0.0, 'full': 0.0}
        
        gc_counts = defaultdict(int)
        for event in events:
            gc_type = event.get('gc_type', 'unknown')
            gc_counts[gc_type] += 1
        
        # 计算频率(次/秒)
        total_frequency = len(events) / time_window
        young_frequency = (gc_counts['young'] + gc_counts['scavenge']) / time_window
        full_frequency = (gc_counts['full'] + gc_counts['global']) / time_window
        
        return {
            'total': total_frequency,
            'young': young_frequency,
            'full': full_frequency
        }
    
    def _calculate_memory_metrics(self, events: List[Dict]) -> Dict[str, float]:
        """计算内存相关指标"""
        heap_utilizations = []
        total_allocated = 0
        total_reclaimed = 0
        
        for event in events:
            heap_before = event.get('heap_before', 0)
            heap_after = event.get('heap_after', 0)
            heap_total = event.get('heap_total', 0)
            
            if heap_total > 0:
                utilization_before = heap_before / heap_total
                heap_utilizations.append(utilization_before)
            
            if heap_before > heap_after:
                reclaimed = heap_before - heap_after
                total_reclaimed += reclaimed
                total_allocated += heap_before  # 简化假设
        
        # 计算指标
        avg_utilization = statistics.mean(heap_utilizations) if heap_utilizations else 0.0
        max_utilization = max(heap_utilizations) if heap_utilizations else 0.0
        
        # 内存分配率和回收效率(简化计算)
        allocation_rate = total_allocated / len(events) if events else 0.0
        reclaim_efficiency = (total_reclaimed / total_allocated * 100) if total_allocated > 0 else 0.0
        
        return {
            'avg_utilization': avg_utilization * 100,
            'max_utilization': max_utilization * 100,
            'allocation_rate': allocation_rate,
            'reclaim_efficiency': reclaim_efficiency
        }
    
    def _calculate_trend_metrics(self, events: List[Dict]) -> Dict[str, str]:
        """计算趋势指标"""
        if len(events) < 3:
            return {'pause_trend': 'stable', 'memory_trend': 'stable'}
        
        # 计算停顿时间趋势
        pause_times = [event.get('pause_time', event.get('duration', 0)) for event in events]
        pause_trend = self._calculate_trend(pause_times)
        
        # 计算内存使用趋势
        memory_usage = [event.get('heap_before', 0) for event in events if event.get('heap_before', 0) > 0]
        memory_trend = self._calculate_trend(memory_usage) if memory_usage else 'stable'
        
        return {
            'pause_trend': pause_trend,
            'memory_trend': memory_trend
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """计算数值序列的趋势"""
        if len(values) < 3:
            return 'stable'
        
        # 使用线性回归斜率判断趋势
        n = len(values)
        x = list(range(n))
        
        # 计算斜率
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(values)
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 'stable'
        
        slope = numerator / denominator
        
        # 判断趋势
        threshold = y_mean * 0.1  # 10%的变化阈值
        if slope > threshold:
            return 'increasing'
        elif slope < -threshold:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_performance_score(self, throughput_metrics: Dict, latency_metrics: Dict, frequency_metrics: Dict) -> float:
        """计算总体性能评分(0-100)"""
        score = 0.0
        
        # 吞吐量权重40%
        throughput_score = min(throughput_metrics['throughput'], 100) * 0.4
        
        # 延迟权重40%
        max_pause = latency_metrics['max']
        if max_pause <= 50:
            latency_score = 100
        elif max_pause <= 100:
            latency_score = 80
        elif max_pause <= 200:
            latency_score = 60
        elif max_pause <= 500:
            latency_score = 40
        else:
            latency_score = 20
        latency_score *= 0.4
        
        # 频率权重20%
        total_freq = frequency_metrics['total']
        if total_freq <= 1:
            frequency_score = 100
        elif total_freq <= 5:
            frequency_score = 80
        elif total_freq <= 10:
            frequency_score = 60
        else:
            frequency_score = 40
        frequency_score *= 0.2
        
        score = throughput_score + latency_score + frequency_score
        return min(max(score, 0), 100)  # 限制在0-100范围内
    
    def _determine_health_status(self, performance_score: float, latency_metrics: Dict) -> str:
        """确定健康状态"""
        max_pause = latency_metrics['max']
        
        if performance_score >= 90 and max_pause <= 100:
            return 'excellent'
        elif performance_score >= 75 and max_pause <= 200:
            return 'good'
        elif performance_score >= 60 and max_pause <= 500:
            return 'warning'
        else:
            return 'critical'
    
    def _percentile(self, sorted_data: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not sorted_data:
            return 0.0
        
        k = (len(sorted_data) - 1) * percentile / 100
        lower = int(math.floor(k))
        upper = int(math.ceil(k))
        
        if lower == upper:
            return sorted_data[lower]
        else:
            d = k - lower
            return sorted_data[lower] * (1 - d) + sorted_data[upper] * d


# 便捷函数
def analyze_gc_metrics(events: List[Dict], time_window: Optional[float] = None) -> GCMetrics:
    """分析GC指标的便捷函数"""
    analyzer = GCMetricsAnalyzer()
    return analyzer.analyze(events, time_window)


if __name__ == '__main__':
    # 简单的测试代码
    sample_events = [
        {'gc_type': 'young', 'pause_time': 15.5, 'heap_before': 512, 'heap_after': 256, 'heap_total': 1024, 'timestamp': 1.0},
        {'gc_type': 'young', 'pause_time': 12.3, 'heap_before': 600, 'heap_after': 300, 'heap_total': 1024, 'timestamp': 5.0},
        {'gc_type': 'mixed', 'pause_time': 25.8, 'heap_before': 800, 'heap_after': 400, 'heap_total': 1024, 'timestamp': 10.0},
    ]
    
    metrics = analyze_gc_metrics(sample_events)
    print(f"性能评分: {metrics.performance_score:.1f}")
    print(f"健康状态: {metrics.health_status}")
    print(f"吞吐量: {metrics.throughput_percentage:.1f}%")
    print(f"P95延迟: {metrics.p95_pause_time:.1f}ms")