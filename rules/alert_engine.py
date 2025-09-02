#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC性能警报引擎
提供可配置的性能阈值检测、异常模式识别和智能警报功能
"""

import json
import statistics
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta


class AlertSeverity(Enum):
    """警报严重程度"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertCategory(Enum):
    """警报类别"""
    PERFORMANCE = "performance"  # 性能问题
    MEMORY = "memory"           # 内存问题
    FREQUENCY = "frequency"     # 频率问题
    TREND = "trend"             # 趋势问题
    STABILITY = "stability"     # 稳定性问题


@dataclass
class AlertRule:
    """警报规则配置"""
    name: str
    description: str
    category: AlertCategory
    severity: AlertSeverity
    condition: str  # 条件表达式
    threshold: float
    enabled: bool = True
    message_template: str = ""
    recommendation: str = ""


@dataclass
class Alert:
    """警报实例"""
    rule_name: str
    category: AlertCategory
    severity: AlertSeverity
    message: str
    actual_value: float
    threshold: float
    recommendation: str
    timestamp: str
    metadata: Dict[str, Any] = None


class GCAlertEngine:
    """GC性能警报引擎"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.rules = self._load_default_rules()
        if config_file:
            self._load_custom_rules(config_file)
        
        self.alerts_history = []
        self.pattern_detector = GCPatternDetector()
    
    def _load_default_rules(self) -> List[AlertRule]:
        """加载默认警报规则"""
        return [
            # 性能相关警报
            AlertRule(
                name="high_pause_time",
                description="GC停顿时间过长",
                category=AlertCategory.PERFORMANCE,
                severity=AlertSeverity.WARNING,
                condition="max_pause_time > threshold",
                threshold=100.0,  # 100ms
                message_template="最大GC停顿时间{actual_value:.1f}ms超过阈值{threshold:.1f}ms",
                recommendation="考虑调整GC参数减少停顿时间，如增加并行GC线程数或优化堆大小设置"
            ),
            AlertRule(
                name="critical_pause_time",
                description="GC停顿时间严重过长",
                category=AlertCategory.PERFORMANCE,
                severity=AlertSeverity.CRITICAL,
                condition="max_pause_time > threshold",
                threshold=500.0,  # 500ms
                message_template="最大GC停顿时间{actual_value:.1f}ms达到危险水平",
                recommendation="立即检查GC配置和应用程序内存使用模式，可能需要重新设计内存分配策略"
            ),
            AlertRule(
                name="low_throughput",
                description="应用吞吐量过低",
                category=AlertCategory.PERFORMANCE,
                severity=AlertSeverity.WARNING,
                condition="throughput_percentage < threshold",
                threshold=95.0,  # 95%
                message_template="应用吞吐量{actual_value:.1f}%低于期望阈值{threshold:.1f}%",
                recommendation="检查GC策略是否合适，考虑调整堆大小或切换到更适合的GC算法"
            ),
            AlertRule(
                name="critical_throughput",
                description="应用吞吐量严重过低",
                category=AlertCategory.PERFORMANCE,
                severity=AlertSeverity.CRITICAL,
                condition="throughput_percentage < threshold",
                threshold=90.0,  # 90%
                message_template="应用吞吐量{actual_value:.1f}%严重低于正常水平",
                recommendation="系统性能严重下降，需要立即优化GC配置或检查是否存在内存泄漏"
            ),
            
            # 频率相关警报
            AlertRule(
                name="high_gc_frequency",
                description="GC频率过高",
                category=AlertCategory.FREQUENCY,
                severity=AlertSeverity.WARNING,
                condition="gc_frequency > threshold",
                threshold=10.0,  # 10次/秒
                message_template="GC频率{actual_value:.1f}次/秒过高",
                recommendation="检查内存分配模式，可能需要增加堆大小或优化对象生命周期管理"
            ),
            AlertRule(
                name="frequent_full_gc",
                description="Full GC频率过高",
                category=AlertCategory.FREQUENCY,
                severity=AlertSeverity.CRITICAL,
                condition="full_gc_frequency > threshold",
                threshold=0.1,  # 0.1次/秒
                message_template="Full GC频率{actual_value:.2f}次/秒过高",
                recommendation="Full GC频繁通常表示堆大小不足或存在内存泄漏，需要立即检查"
            ),
            
            # 内存相关警报
            AlertRule(
                name="high_heap_utilization",
                description="堆内存利用率过高",
                category=AlertCategory.MEMORY,
                severity=AlertSeverity.WARNING,
                condition="max_heap_utilization > threshold",
                threshold=85.0,  # 85%
                message_template="最大堆利用率{actual_value:.1f}%过高",
                recommendation="考虑增加堆大小或优化内存使用效率"
            ),
            AlertRule(
                name="poor_memory_reclaim",
                description="内存回收效率低下",
                category=AlertCategory.MEMORY,
                severity=AlertSeverity.WARNING,
                condition="memory_reclaim_efficiency < threshold",
                threshold=50.0,  # 50%
                message_template="内存回收效率{actual_value:.1f}%低于预期",
                recommendation="检查是否存在内存泄漏或大量长期存活的对象"
            ),
            
            # 趋势相关警报
            AlertRule(
                name="degrading_pause_trend",
                description="GC停顿时间呈恶化趋势",
                category=AlertCategory.TREND,
                severity=AlertSeverity.WARNING,
                condition="pause_time_trend == 'increasing'",
                threshold=0.0,
                message_template="GC停顿时间呈上升趋势",
                recommendation="监控内存使用情况，可能需要调整堆大小或检查内存泄漏"
            ),
            AlertRule(
                name="memory_leak_pattern",
                description="疑似内存泄漏模式",
                category=AlertCategory.TREND,
                severity=AlertSeverity.CRITICAL,
                condition="memory_usage_trend == 'increasing'",
                threshold=0.0,
                message_template="内存使用呈持续上升趋势，疑似内存泄漏",
                recommendation="立即检查应用程序是否存在内存泄漏，使用内存分析工具进行详细诊断"
            ),
            
            # 稳定性相关警报
            AlertRule(
                name="unstable_performance",
                description="性能不稳定",
                category=AlertCategory.STABILITY,
                severity=AlertSeverity.WARNING,
                condition="p99_pause_time / avg_pause_time > threshold",
                threshold=3.0,  # P99是平均值的3倍以上
                message_template="GC性能不稳定，P99停顿时间是平均值的{actual_value:.1f}倍",
                recommendation="检查是否有突发性的内存分配或GC触发模式"
            )
        ]
    
    def _load_custom_rules(self, config_file: str):
        """加载自定义警报规则"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for rule_data in config.get('custom_rules', []):
                rule = AlertRule(
                    name=rule_data['name'],
                    description=rule_data['description'],
                    category=AlertCategory(rule_data['category']),
                    severity=AlertSeverity(rule_data['severity']),
                    condition=rule_data['condition'],
                    threshold=rule_data['threshold'],
                    enabled=rule_data.get('enabled', True),
                    message_template=rule_data.get('message_template', ''),
                    recommendation=rule_data.get('recommendation', '')
                )
                self.rules.append(rule)
        
        except Exception as e:
            print(f"加载自定义规则失败: {e}")
    
    def evaluate_metrics(self, metrics: Any) -> List[Alert]:
        """评估性能指标并生成警报"""
        alerts = []
        current_time = datetime.now().isoformat()
        
        # 基础指标检查
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            alert = self._evaluate_rule(rule, metrics, current_time)
            if alert:
                alerts.append(alert)
        
        # 模式检测
        pattern_alerts = self.pattern_detector.detect_patterns(metrics)
        alerts.extend(pattern_alerts)
        
        # 保存到历史记录
        self.alerts_history.extend(alerts)
        
        return alerts
    
    def _evaluate_rule(self, rule: AlertRule, metrics: Any, timestamp: str) -> Optional[Alert]:
        """评估单个规则"""
        try:
            # 获取相关指标值
            if "max_pause_time" in rule.condition:
                actual_value = metrics.max_pause_time
            elif "throughput_percentage" in rule.condition:
                actual_value = metrics.throughput_percentage
            elif "gc_frequency" in rule.condition:
                actual_value = metrics.gc_frequency
            elif "full_gc_frequency" in rule.condition:
                actual_value = metrics.full_gc_frequency
            elif "max_heap_utilization" in rule.condition:
                actual_value = metrics.max_heap_utilization
            elif "memory_reclaim_efficiency" in rule.condition:
                actual_value = metrics.memory_reclaim_efficiency
            elif "pause_time_trend" in rule.condition:
                if metrics.pause_time_trend == "increasing":
                    actual_value = 1.0
                else:
                    return None
            elif "memory_usage_trend" in rule.condition:
                if metrics.memory_usage_trend == "increasing":
                    actual_value = 1.0
                else:
                    return None
            elif "p99_pause_time / avg_pause_time" in rule.condition:
                if metrics.avg_pause_time > 0:
                    actual_value = metrics.p99_pause_time / metrics.avg_pause_time
                else:
                    return None
            else:
                return None
            
            # 评估条件
            if self._evaluate_condition(rule.condition, actual_value, rule.threshold):
                message = rule.message_template.format(
                    actual_value=actual_value,
                    threshold=rule.threshold
                )
                
                return Alert(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    message=message,
                    actual_value=actual_value,
                    threshold=rule.threshold,
                    recommendation=rule.recommendation,
                    timestamp=timestamp
                )
        
        except Exception as e:
            print(f"评估规则 {rule.name} 时出错: {e}")
        
        return None
    
    def _evaluate_condition(self, condition: str, actual_value: float, threshold: float) -> bool:
        """评估条件表达式"""
        if ">" in condition:
            return actual_value > threshold
        elif "<" in condition:
            return actual_value < threshold
        elif "==" in condition:
            return abs(actual_value - threshold) < 0.001
        else:
            return False
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Alert]:
        """按严重程度获取警报"""
        return [alert for alert in self.alerts_history if alert.severity == severity]
    
    def get_alerts_by_category(self, category: AlertCategory) -> List[Alert]:
        """按类别获取警报"""
        return [alert for alert in self.alerts_history if alert.category == category]
    
    def generate_alert_summary(self, alerts: List[Alert]) -> str:
        """生成警报摘要报告"""
        if not alerts:
            return "🎉 没有发现性能警报，系统运行正常！"
        
        # 按严重程度分组
        by_severity = {}
        for alert in alerts:
            if alert.severity not in by_severity:
                by_severity[alert.severity] = []
            by_severity[alert.severity].append(alert)
        
        summary = "## 🚨 GC性能警报摘要\n\n"
        
        # 总体统计
        summary += f"**总警报数**: {len(alerts)}\n"
        for severity in AlertSeverity:
            count = len(by_severity.get(severity, []))
            if count > 0:
                emoji = self._get_severity_emoji(severity)
                summary += f"- {emoji} {severity.value.title()}: {count}个\n"
        
        summary += "\n"
        
        # 详细警报
        for severity in [AlertSeverity.EMERGENCY, AlertSeverity.CRITICAL, AlertSeverity.WARNING, AlertSeverity.INFO]:
            severity_alerts = by_severity.get(severity, [])
            if severity_alerts:
                emoji = self._get_severity_emoji(severity)
                summary += f"### {emoji} {severity.value.title()} 级警报\n\n"
                
                for alert in severity_alerts:
                    summary += f"**{alert.message}**\n"
                    summary += f"- 类别: {alert.category.value}\n"
                    summary += f"- 建议: {alert.recommendation}\n\n"
        
        return summary
    
    def _get_severity_emoji(self, severity: AlertSeverity) -> str:
        """获取严重程度对应的emoji"""
        return {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🔥",
            AlertSeverity.EMERGENCY: "🚨"
        }.get(severity, "❓")
    
    def export_alerts(self, format: str = "json") -> str:
        """导出警报数据"""
        if format == "json":
            return json.dumps(
                [asdict(alert) for alert in self.alerts_history],
                indent=2,
                ensure_ascii=False
            )
        else:
            raise ValueError(f"不支持的导出格式: {format}")


class GCPatternDetector:
    """GC模式检测器"""
    
    def detect_patterns(self, metrics: Any) -> List[Alert]:
        """检测异常模式"""
        alerts = []
        current_time = datetime.now().isoformat()
        
        # 检测性能退化模式
        if self._detect_performance_degradation(metrics):
            alerts.append(Alert(
                rule_name="performance_degradation",
                category=AlertCategory.TREND,
                severity=AlertSeverity.WARNING,
                message="检测到性能退化模式：GC效率逐步下降",
                actual_value=metrics.performance_score,
                threshold=80.0,
                recommendation="建议检查内存使用模式和GC配置，可能需要进行内存优化",
                timestamp=current_time
            ))
        
        # 检测异常停顿模式
        if self._detect_abnormal_pause_pattern(metrics):
            alerts.append(Alert(
                rule_name="abnormal_pause_pattern",
                category=AlertCategory.STABILITY,
                severity=AlertSeverity.WARNING,
                message="检测到异常停顿模式：停顿时间波动较大",
                actual_value=metrics.max_pause_time - metrics.min_pause_time,
                threshold=100.0,
                recommendation="检查是否有突发性的大对象分配或系统资源竞争",
                timestamp=current_time
            ))
        
        return alerts
    
    def _detect_performance_degradation(self, metrics: Any) -> bool:
        """检测性能退化"""
        # 简单的性能退化检测：性能评分低且趋势恶化
        return (metrics.performance_score < 80 and 
                metrics.pause_time_trend == "increasing")
    
    def _detect_abnormal_pause_pattern(self, metrics: Any) -> bool:
        """检测异常停顿模式"""
        # 停顿时间变异系数较大
        if metrics.avg_pause_time > 0:
            pause_range = metrics.max_pause_time - metrics.min_pause_time
            return pause_range > metrics.avg_pause_time * 2
        return False


# 便捷函数
def create_alert_engine(config_file: Optional[str] = None) -> GCAlertEngine:
    """创建警报引擎实例"""
    return GCAlertEngine(config_file)


def evaluate_gc_alerts(metrics: Any, config_file: Optional[str] = None) -> List[Alert]:
    """评估GC指标并返回警报列表"""
    engine = create_alert_engine(config_file)
    return engine.evaluate_metrics(metrics)


if __name__ == '__main__':
    # 示例用法
    import sys
    import os
    
    # 添加项目根目录到Python路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    
    from analyzer.metrics import GCMetrics
    
    # 创建示例指标
    sample_metrics = GCMetrics(
        throughput_percentage=92.0,
        gc_overhead_percentage=8.0,
        avg_pause_time=45.0,
        p50_pause_time=30.0,
        p95_pause_time=80.0,
        p99_pause_time=120.0,
        max_pause_time=150.0,
        min_pause_time=10.0,
        gc_frequency=8.5,
        young_gc_frequency=7.0,
        full_gc_frequency=0.15,
        avg_heap_utilization=78.0,
        max_heap_utilization=88.0,
        memory_allocation_rate=100.0,
        memory_reclaim_efficiency=65.0,
        pause_time_trend="increasing",
        memory_usage_trend="stable",
        performance_score=75.0,
        health_status="warning"
    )
    
    # 评估警报
    engine = create_alert_engine()
    alerts = engine.evaluate_metrics(sample_metrics)
    
    print("检测到的警报:")
    for alert in alerts:
        print(f"- {alert.severity.value}: {alert.message}")
    
    print("\n警报摘要:")
    print(engine.generate_alert_summary(alerts))