#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC停顿分布分析器
生成停顿时间直方图数据，用于分析GC停顿时间的分布特征
"""

import math
from typing import List, Dict, Tuple, Optional
from collections import defaultdict


class PauseDistributionAnalyzer:
    """GC停顿分布分析器"""
    
    def __init__(self):
        # 预定义的停顿时间区间（毫秒）
        self.default_bins = [
            (0, 5, "0-5ms"),
            (5, 10, "5-10ms"), 
            (10, 20, "10-20ms"),
            (20, 50, "20-50ms"),
            (50, 100, "50-100ms"),
            (100, 200, "100-200ms"),
            (200, 500, "200-500ms"),
            (500, 1000, "500ms-1s"),
            (1000, float('inf'), ">1s")
        ]
    
    def analyze_pause_distribution(self, events: List[Dict], custom_bins: Optional[List[Tuple]] = None) -> Dict:
        """
        分析GC停顿时间分布
        
        Args:
            events: GC事件列表
            custom_bins: 自定义区间，格式[(min, max, label), ...]
            
        Returns:
            分布分析结果字典
        """
        pause_times = self._extract_pause_times(events)
        
        if not pause_times:
            return self._empty_distribution()
        
        # 选择使用的区间
        bins = custom_bins if custom_bins else self.default_bins
        
        # 计算分布
        distribution = self._calculate_distribution(pause_times, bins)
        
        # 计算统计信息
        stats = self._calculate_distribution_stats(pause_times, distribution)
        
        return {
            'distribution': distribution,
            'statistics': stats,
            'total_events': len(pause_times),
            'bins_used': [bin_info[2] for bin_info in bins],
            'raw_data': pause_times
        }
    
    def _extract_pause_times(self, events: List[Dict]) -> List[float]:
        """从事件中提取停顿时间"""
        pause_times = []
        for event in events:
            # 支持不同的字段名
            pause_time = event.get('pause_time') or event.get('duration') or event.get('time')
            if pause_time is not None and pause_time > 0:
                pause_times.append(float(pause_time))
        return pause_times
    
    def _calculate_distribution(self, pause_times: List[float], bins: List[Tuple]) -> List[Dict]:
        """计算停顿时间分布"""
        distribution = []
        total_count = len(pause_times)
        
        for min_val, max_val, label in bins:
            count = sum(1 for t in pause_times if min_val <= t < max_val)
            percentage = (count / total_count * 100) if total_count > 0 else 0
            
            distribution.append({
                'label': label,
                'min_value': min_val,
                'max_value': max_val if max_val != float('inf') else None,
                'count': count,
                'percentage': round(percentage, 2),
                'cumulative_count': 0,  # 将在后续计算
                'cumulative_percentage': 0.0
            })
        
        # 计算累积统计
        cumulative_count = 0
        for item in distribution:
            cumulative_count += item['count']
            item['cumulative_count'] = cumulative_count
            item['cumulative_percentage'] = round(
                (cumulative_count / total_count * 100) if total_count > 0 else 0, 2
            )
        
        return distribution
    
    def _calculate_distribution_stats(self, pause_times: List[float], distribution: List[Dict]) -> Dict:
        """计算分布统计信息"""
        if not pause_times:
            return {}
        
        pause_times_sorted = sorted(pause_times)
        
        stats = {
            'mean': sum(pause_times) / len(pause_times),
            'median': self._median(pause_times_sorted),
            'std_dev': self._std_deviation(pause_times),
            'min': min(pause_times),
            'max': max(pause_times),
            'range': max(pause_times) - min(pause_times),
            'skewness': self._calculate_skewness(pause_times),
            'concentration_index': self._calculate_concentration_index(distribution)
        }
        
        # 格式化统计值
        for key, value in stats.items():
            if isinstance(value, float):
                stats[key] = round(value, 3)
        
        return stats
    
    def _median(self, sorted_values: List[float]) -> float:
        """计算中位数"""
        n = len(sorted_values)
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    def _std_deviation(self, values: List[float]) -> float:
        """计算标准差"""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def _calculate_skewness(self, values: List[float]) -> float:
        """计算偏度（衡量分布的对称性）"""
        if len(values) < 3:
            return 0.0
        
        mean = sum(values) / len(values)
        std_dev = self._std_deviation(values)
        
        if std_dev == 0:
            return 0.0
        
        n = len(values)
        skewness = (n / ((n - 1) * (n - 2))) * sum(((x - mean) / std_dev) ** 3 for x in values)
        return skewness
    
    def _calculate_concentration_index(self, distribution: List[Dict]) -> float:
        """计算集中度指数（大部分停顿时间是否集中在少数几个区间）"""
        total_count = sum(item['count'] for item in distribution)
        if total_count == 0:
            return 0.0
        
        # 找到包含80%事件的区间数量
        cumulative = 0
        bins_for_80_percent = 0
        
        for item in distribution:
            cumulative += item['count']
            bins_for_80_percent += 1
            if cumulative >= total_count * 0.8:
                break
        
        # 集中度 = 1 - (需要的区间数 / 总区间数)
        total_bins = len([item for item in distribution if item['count'] > 0])
        concentration = 1 - (bins_for_80_percent / total_bins) if total_bins > 0 else 0
        return max(0, min(1, concentration))
    
    def _empty_distribution(self) -> Dict:
        """返回空分布结果"""
        return {
            'distribution': [],
            'statistics': {},
            'total_events': 0,
            'bins_used': [],
            'raw_data': []
        }
    
    def create_adaptive_bins(self, pause_times: List[float], num_bins: int = 8) -> List[Tuple]:
        """根据数据自适应创建区间"""
        if not pause_times or num_bins <= 0:
            return self.default_bins
        
        pause_times_sorted = sorted(pause_times)
        min_val = pause_times_sorted[0]
        max_val = pause_times_sorted[-1]
        
        if min_val == max_val:
            return [(min_val, min_val + 1, f"{min_val:.1f}ms")]
        
        # 使用对数尺度或线性尺度
        if max_val / min_val > 10:  # 使用对数尺度
            return self._create_log_bins(min_val, max_val, num_bins)
        else:  # 使用线性尺度
            return self._create_linear_bins(min_val, max_val, num_bins)
    
    def _create_linear_bins(self, min_val: float, max_val: float, num_bins: int) -> List[Tuple]:
        """创建线性区间"""
        bins = []
        step = (max_val - min_val) / num_bins
        
        for i in range(num_bins):
            start = min_val + i * step
            end = min_val + (i + 1) * step if i < num_bins - 1 else max_val + 0.1
            label = f"{start:.1f}-{end:.1f}ms"
            bins.append((start, end, label))
        
        return bins
    
    def _create_log_bins(self, min_val: float, max_val: float, num_bins: int) -> List[Tuple]:
        """创建对数区间"""
        bins = []
        log_min = math.log10(max(min_val, 0.1))
        log_max = math.log10(max_val)
        log_step = (log_max - log_min) / num_bins
        
        for i in range(num_bins):
            start = 10 ** (log_min + i * log_step)
            end = 10 ** (log_min + (i + 1) * log_step) if i < num_bins - 1 else max_val + 0.1
            
            if start < 1:
                label = f"{start:.2f}-{end:.2f}ms"
            else:
                label = f"{start:.1f}-{end:.1f}ms"
            
            bins.append((start, end, label))
        
        return bins
    
    def generate_chart_data(self, distribution_result: Dict) -> Dict:
        """生成适用于图表的数据格式"""
        distribution = distribution_result.get('distribution', [])
        
        if not distribution:
            return {'labels': [], 'counts': [], 'percentages': []}
        
        labels = [item['label'] for item in distribution if item['count'] > 0]
        counts = [item['count'] for item in distribution if item['count'] > 0]
        percentages = [item['percentage'] for item in distribution if item['count'] > 0]
        
        return {
            'labels': labels,
            'counts': counts,
            'percentages': percentages,
            'total_events': distribution_result.get('total_events', 0),
            'statistics': distribution_result.get('statistics', {})
        }
    
    def format_distribution_summary(self, distribution_result: Dict) -> str:
        """格式化分布摘要文本"""
        stats = distribution_result.get('statistics', {})
        distribution = distribution_result.get('distribution', [])
        total_events = distribution_result.get('total_events', 0)
        
        if not stats or total_events == 0:
            return "无有效的停顿时间数据"
        
        summary_lines = []
        summary_lines.append(f"📊 停顿时间分布分析（共 {total_events} 次GC）")
        summary_lines.append("")
        
        # 基础统计
        summary_lines.append("📈 基础统计:")
        summary_lines.append(f"  平均停顿: {stats.get('mean', 0):.2f}ms")
        summary_lines.append(f"  中位数: {stats.get('median', 0):.2f}ms")
        summary_lines.append(f"  标准差: {stats.get('std_dev', 0):.2f}ms")
        summary_lines.append(f"  最小值: {stats.get('min', 0):.2f}ms")
        summary_lines.append(f"  最大值: {stats.get('max', 0):.2f}ms")
        
        # 分布特征
        skewness = stats.get('skewness', 0)
        concentration = stats.get('concentration_index', 0)
        
        summary_lines.append("")
        summary_lines.append("🔍 分布特征:")
        if skewness > 0.5:
            summary_lines.append("  分布特征: 右偏分布（少数长停顿）")
        elif skewness < -0.5:
            summary_lines.append("  分布特征: 左偏分布（停顿时间均匀）")
        else:
            summary_lines.append("  分布特征: 对称分布")
        
        if concentration > 0.7:
            summary_lines.append("  集中度: 高（大部分停顿时间集中在少数区间）")
        elif concentration > 0.4:
            summary_lines.append("  集中度: 中等")
        else:
            summary_lines.append("  集中度: 低（停顿时间分散）")
        
        # 主要分布区间
        summary_lines.append("")
        summary_lines.append("🎯 主要分布区间:")
        sorted_distribution = sorted(distribution, key=lambda x: x['count'], reverse=True)
        for item in sorted_distribution[:3]:
            if item['count'] > 0:
                summary_lines.append(f"  {item['label']}: {item['count']}次 ({item['percentage']:.1f}%)")
        
        return "\n".join(summary_lines)


# 示例使用
if __name__ == "__main__":
    # 测试数据
    sample_events = [
        {'pause_time': 12.3}, {'pause_time': 8.7}, {'pause_time': 15.2},
        {'pause_time': 45.1}, {'pause_time': 9.8}, {'pause_time': 156.7},
        {'pause_time': 11.4}, {'pause_time': 23.6}, {'pause_time': 7.9}
    ]
    
    analyzer = PauseDistributionAnalyzer()
    result = analyzer.analyze_pause_distribution(sample_events)
    
    print("停顿时间分布分析结果:")
    print(analyzer.format_distribution_summary(result))
    
    print("\n图表数据:")
    chart_data = analyzer.generate_chart_data(result)
    print(f"区间标签: {chart_data['labels']}")
    print(f"事件数量: {chart_data['counts']}")
    print(f"百分比: {chart_data['percentages']}")