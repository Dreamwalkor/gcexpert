#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint 4高级分析特性测试用例
测试警报引擎和报告生成功能
"""

import os
import sys
import tempfile
import asyncio

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from rules.alert_engine import GCAlertEngine, AlertRule
from analyzer.report_generator import GCReportGenerator, generate_gc_report
from main import generate_gc_report_tool


class MockMetrics:
    """模拟指标对象，包含所有必需的属性"""
    def __init__(self):
        self.max_pause_time = 180.0
        self.min_pause_time = 15.0
        self.throughput_percentage = 88.5
        self.gc_frequency = 1.5
        self.full_gc_frequency = 0.0
        self.max_heap_utilization = 75.0
        self.memory_reclaim_efficiency = 45.2
        self.pause_time_trend = "increasing"
        self.memory_usage_trend = "stable"
        self.avg_pause_time = 73.5
        self.p99_pause_time = 175.0
        self.p50_pause_time = 65.0
        self.p95_pause_time = 165.0
        self.performance_score = 72.5
        self.gc_overhead_percentage = 11.5
        self.young_gc_frequency = 1.0
        self.avg_heap_utilization = 62.5
        self.memory_allocation_rate = 256.0
        self.health_status = "Warning"


class TestSprint4Features:
    """Sprint 4功能测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.alert_engine = GCAlertEngine()
        self.report_generator = GCReportGenerator()
        
        # 准备测试数据
        self.test_events = [
            {
                'timestamp': 1.0,
                'gc_type': 'young',
                'pause_time': 15.5,
                'heap_before': 1024,
                'heap_after': 512,
                'heap_size': 2048
            },
            {
                'timestamp': 2.0,
                'gc_type': 'young',
                'pause_time': 180.0,  # 过长停顿
                'heap_before': 1536,
                'heap_after': 768,
                'heap_size': 2048
            },
            {
                'timestamp': 3.0,
                'gc_type': 'mixed',
                'pause_time': 25.0,
                'heap_before': 1280,
                'heap_after': 640,
                'heap_size': 2048
            }
        ]
        
        self.test_metrics = {
            'throughput': {
                'app_time_percentage': 88.5,
                'gc_time_percentage': 11.5
            },
            'latency': {
                'avg_pause_time': 73.5,
                'max_pause_time': 180.0,
                'p50_pause_time': 25.0,
                'p95_pause_time': 155.0,
                'p99_pause_time': 175.0,
                'min_pause_time': 15.5
            },
            'frequency': {
                'gc_frequency': 1.5,
                'young_gc_frequency': 1.0,
                'full_gc_frequency': 0.0
            },
            'memory': {
                'avg_heap_utilization': 62.5,
                'max_heap_utilization': 75.0,
                'memory_allocation_rate': 256.0,
                'memory_reclaim_efficiency': 45.2
            }
        }
        
        self.test_analysis = {
            'gc_type': 'G1 GC',
            'file_path': '/tmp/test.log',
            'total_events': 3
        }
    
    def test_alert_engine_basic(self):
        """测试警报引擎基础功能"""
        print("🧪 测试警报引擎基础功能...")
        
        mock_metrics = MockMetrics()
        
        # 分析指标
        alerts = self.alert_engine.evaluate_metrics(mock_metrics)
        
        # 验证返回的警报
        assert len(alerts) > 0, "应该检测到警报"
        
        # 检查是否有高停顿时间警报
        pause_alerts = [a for a in alerts if '停顿时间' in a.message]
        assert len(pause_alerts) > 0, "应该检测到停顿时间警报"
        
        print(f"✅ 检测到 {len(alerts)} 个警报")
        for alert in alerts:
            print(f"   - {alert.severity.value}: {alert.message}")
    
    def test_alert_engine_custom_rules(self):
        """测试警报引擎自定义规则"""
        print("🧪 测试警报引擎自定义规则...")
        
        from rules.alert_engine import AlertRule, AlertCategory, AlertSeverity
        
        # 添加自定义规则
        custom_rule = AlertRule(
            name="test_memory_rule",
            description="内存使用过高测试",
            category=AlertCategory.MEMORY,
            severity=AlertSeverity.WARNING,
            condition="max_heap_utilization > threshold",
            threshold=70.0,  # 降低阈值以触发警报
            message_template="自定义内存规则触发: {actual_value:.1f}%",
            recommendation="这是一个测试规则"
        )
        
        # 创建带自定义规则的引擎
        engine = GCAlertEngine()
        engine.rules.append(custom_rule)
        
        # 创建一个低堆利用率的Mock对象
        class LowHeapMockMetrics(MockMetrics):
            def __init__(self):
                super().__init__()
                self.max_heap_utilization = 75.0  # 超过自定义阈值70%
                self.max_pause_time = 50.0  # 低于默认阈值
                self.throughput_percentage = 96.0  # 高于默认阈值
        
        mock_metrics = LowHeapMockMetrics()
        
        # 分析指标
        alerts = engine.evaluate_metrics(mock_metrics)
        
        # 验证自定义规则触发
        memory_alerts = [a for a in alerts if '自定义内存规则' in a.message]
        assert len(memory_alerts) > 0, "自定义内存规则应该触发"
        
        print(f"✅ 自定义规则成功触发")
    
    def test_report_generator_markdown(self):
        """测试Markdown报告生成"""
        print("🧪 测试Markdown报告生成...")
        
        mock_metrics = MockMetrics()
        
        # 生成测试警报
        alerts = self.alert_engine.evaluate_metrics(mock_metrics)
        alerts_data = [{
            'severity': alert.severity.value,
            'category': alert.category.value,
            'message': alert.message,
            'details': alert.recommendation
        } for alert in alerts]
        
        # 生成Markdown报告
        report = self.report_generator.generate_markdown_report(
            analysis_data=self.test_analysis,
            metrics_data=self.test_metrics,
            alerts_data=alerts_data
        )
        
        # 验证报告内容
        assert "# GC性能分析报告" in report, "应该包含报告标题"
        assert "G1 GC" in report, "应该包含GC类型"
        assert "📈 关键性能指标" in report, "应该包含性能指标"
        assert "⚠️ 性能警报" in report, "应该包含警报信息"
        assert "💡 优化建议" in report, "应该包含优化建议"
        
        print("✅ Markdown报告生成成功")
        print(f"   报告长度: {len(report)} 字符")
    
    def test_report_generator_html(self):
        """测试HTML报告生成"""
        print("🧪 测试HTML报告生成...")
        
        # 生成HTML报告
        report = self.report_generator.generate_html_report(
            analysis_data=self.test_analysis,
            metrics_data=self.test_metrics,
            alerts_data=[]
        )
        
        # 验证HTML结构
        assert "<!DOCTYPE html>" in report, "应该包含HTML声明"
        assert "<title>GC性能分析报告</title>" in report, "应该包含标题"
        assert "🔍 GC性能分析报告" in report, "应该包含报告标题"
        assert "📊 基本信息" in report, "应该包含基本信息"
        assert "📈 关键性能指标" in report, "应该包含性能指标"
        
        print("✅ HTML报告生成成功")
        print(f"   报告长度: {len(report)} 字符")
    
    def test_report_save_functionality(self):
        """测试报告保存功能"""
        print("🧪 测试报告保存功能...")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 测试Markdown保存
            md_file = os.path.join(temp_dir, "test_report")
            report = self.report_generator.generate_markdown_report(
                analysis_data=self.test_analysis,
                metrics_data=self.test_metrics
            )
            
            success = self.report_generator.save_report(report, md_file, "markdown")
            assert success, "Markdown报告保存应该成功"
            assert os.path.exists(md_file + ".md"), "Markdown文件应该存在"
            
            # 测试HTML保存
            html_file = os.path.join(temp_dir, "test_report")
            html_report = self.report_generator.generate_html_report(
                analysis_data=self.test_analysis,
                metrics_data=self.test_metrics
            )
            
            success = self.report_generator.save_report(html_report, html_file, "html")
            assert success, "HTML报告保存应该成功"
            assert os.path.exists(html_file + ".html"), "HTML文件应该存在"
            
            print("✅ 报告保存功能正常")
    
    def test_generate_gc_report_convenience_function(self):
        """测试便利函数"""
        print("🧪 测试便利函数...")
        
        # 测试Markdown生成
        md_report = generate_gc_report(
            analysis_data=self.test_analysis,
            metrics_data=self.test_metrics,
            format_type="markdown"
        )
        
        assert "# GC性能分析报告" in md_report, "便利函数应该生成正确的Markdown"
        
        # 测试HTML生成
        html_report = generate_gc_report(
            analysis_data=self.test_analysis,
            metrics_data=self.test_metrics,
            format_type="html"
        )
        
        assert "<!DOCTYPE html>" in html_report, "便利函数应该生成正确的HTML"
        
        print("✅ 便利函数工作正常")
    
    def test_mcp_generate_report_tool(self):
        """测试MCP报告生成工具（模拟）"""
        print("🧪 测试MCP报告生成工具...")
        
        # 由于需要全局状态，这里只测试参数验证
        from main import current_analysis_result
        
        # 模拟设置全局状态
        original_result = current_analysis_result
        
        try:
            # 测试无分析结果的情况
            import main
            main.current_analysis_result = None
            
            async def test_no_analysis():
                try:
                    await generate_gc_report_tool({})
                    assert False, "应该抛出错误"
                except ValueError as e:
                    assert "请先使用analyze_gc_log工具" in str(e)
                    return True
                return False
            
            result = asyncio.run(test_no_analysis())
            assert result, "无分析结果应该抛出正确错误"
            
            print("✅ MCP工具参数验证正常")
            
        finally:
            # 恢复原始状态
            import main
            main.current_analysis_result = original_result
    
    def test_integration_workflow(self):
        """测试完整工作流程"""
        print("🧪 测试完整工作流程...")
        
        mock_metrics = MockMetrics()
        
        # 1. 警报分析
        alerts = self.alert_engine.evaluate_metrics(mock_metrics)
        assert len(alerts) > 0, "应该生成警报"
        
        # 2. 转换警报数据
        alerts_data = [{
            'severity': alert.severity.value,
            'category': alert.category.value,
            'message': alert.message,
            'details': alert.recommendation
        } for alert in alerts]
        
        # 3. 生成完整报告
        report = generate_gc_report(
            analysis_data=self.test_analysis,
            metrics_data=self.test_metrics,
            alerts_data=alerts_data,
            format_type="markdown"
        )
        
        # 验证完整报告
        assert "# GC性能分析报告" in report
        assert "📈 关键性能指标" in report
        assert "⚠️ 性能警报" in report
        assert "💡 优化建议" in report
        
        # 验证警报内容被包含
        assert any(alert['message'] in report for alert in alerts_data), "警报信息应该在报告中"
        
        print("✅ 完整工作流程测试通过")


def run_sprint4_tests():
    """运行Sprint 4的所有测试"""
    test_instance = TestSprint4Features()
    test_instance.setup_method()
    
    tests = [
        ("警报引擎基础功能", test_instance.test_alert_engine_basic),
        ("警报引擎自定义规则", test_instance.test_alert_engine_custom_rules),
        ("Markdown报告生成", test_instance.test_report_generator_markdown),
        ("HTML报告生成", test_instance.test_report_generator_html),
        ("报告保存功能", test_instance.test_report_save_functionality),
        ("便利函数", test_instance.test_generate_gc_report_convenience_function),
        ("MCP工具参数验证", test_instance.test_mcp_generate_report_tool),
        ("完整工作流程", test_instance.test_integration_workflow),
    ]
    
    passed = 0
    total = len(tests)
    
    print("🚀 开始Sprint 4高级分析特性测试...\n")
    
    for test_name, test_func in tests:
        print(f"🧪 运行测试: {test_name}")
        try:
            test_func()
            passed += 1
            print(f"✅ {test_name} 测试通过\n")
        except Exception as e:
            print(f"❌ {test_name} 测试失败: {e}\n")
    
    print(f"📊 Sprint 4测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 Sprint 4所有测试通过！")
        return True
    else:
        print("⚠️ 部分测试失败，需要检查问题")
        return False


if __name__ == "__main__":
    success = run_sprint4_tests()
    sys.exit(0 if success else 1)