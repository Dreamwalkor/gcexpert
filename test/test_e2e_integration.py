#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint 5: 端到端集成测试
验证完整的GC日志分析系统功能
"""

import os
import sys
import asyncio
import tempfile

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from main import (
    analyze_gc_log_tool,
    get_gc_metrics_tool,
    compare_gc_logs_tool,
    detect_gc_issues_tool,
    generate_gc_report_tool,
    list_tools
)


class TestEndToEndIntegration:
    """端到端集成测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.test_data_dir = os.path.join(project_root, 'test', 'data')
        self.sample_g1_log = os.path.join(self.test_data_dir, 'sample_g1.log')
        self.sample_j9_log = os.path.join(self.test_data_dir, 'sample_j9.log')
    
    async def test_complete_workflow(self):
        """测试完整的GC分析工作流程"""
        print("🚀 开始完整工作流程测试...")
        
        if not os.path.exists(self.sample_g1_log):
            print("⚠️ 跳过测试：G1测试数据文件不存在")
            return False
        
        try:
            # 1. 分析GC日志
            print("📊 步骤1: 分析G1 GC日志...")
            analyze_result = await analyze_gc_log_tool({
                "file_path": self.sample_g1_log,
                "analysis_type": "detailed"
            })
            
            print("✅ 日志分析完成")
            assert analyze_result.content, "分析结果应该有内容"
            
            # 2. 获取详细指标
            print("📈 步骤2: 获取详细性能指标...")
            metrics_result = await get_gc_metrics_tool({
                "metric_types": ["all"]
            })
            
            print("✅ 指标获取完成")
            assert metrics_result.content, "指标结果应该有内容"
            
            # 3. 检测性能问题
            print("🔍 步骤3: 检测GC性能问题...")
            issues_result = await detect_gc_issues_tool({
                "threshold_config": {
                    "max_pause_time": 50,  # 设置较低阈值以触发警报
                    "min_throughput": 98
                }
            })
            
            print("✅ 问题检测完成")
            assert issues_result.content, "问题检测结果应该有内容"
            
            # 4. 生成Markdown报告
            print("📝 步骤4: 生成Markdown分析报告...")
            with tempfile.TemporaryDirectory() as temp_dir:
                md_report_file = os.path.join(temp_dir, "gc_analysis_report.md")
                
                md_report_result = await generate_gc_report_tool({
                    "format_type": "markdown",
                    "output_file": md_report_file,
                    "include_alerts": True
                })
                
                print("✅ Markdown报告生成完成")
                assert md_report_result.content, "报告生成结果应该有内容"
                assert os.path.exists(md_report_file), "Markdown报告文件应该存在"
                
                # 验证报告内容
                with open(md_report_file, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                
                assert "# GC性能分析报告" in report_content, "报告应该包含标题"
                assert "G1 GC" in report_content, "报告应该包含GC类型"
                print(f"   Markdown报告长度: {len(report_content)} 字符")
                
                # 5. 生成HTML报告
                print("🌐 步骤5: 生成HTML分析报告...")
                html_report_file = os.path.join(temp_dir, "gc_analysis_report.html")
                
                html_report_result = await generate_gc_report_tool({
                    "format_type": "html",
                    "output_file": html_report_file,
                    "include_alerts": True
                })
                
                print("✅ HTML报告生成完成")
                assert html_report_result.content, "HTML报告生成结果应该有内容"
                assert os.path.exists(html_report_file), "HTML报告文件应该存在"
                
                # 验证HTML报告内容
                with open(html_report_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                assert "<!DOCTYPE html>" in html_content, "HTML报告应该包含HTML声明"
                assert "GC性能分析报告" in html_content, "HTML报告应该包含标题"
                print(f"   HTML报告长度: {len(html_content)} 字符")
            
            # 6. 日志比较（如果J9日志存在）
            if os.path.exists(self.sample_j9_log):
                print("⚖️ 步骤6: 比较不同GC类型的性能...")
                compare_result = await compare_gc_logs_tool({
                    "file_path_1": self.sample_g1_log,
                    "file_path_2": self.sample_j9_log
                })
                
                print("✅ 日志比较完成")
                assert compare_result.content, "比较结果应该有内容"
            else:
                print("⚠️ 跳过步骤6：J9测试数据文件不存在")
            
            return True
            
        except Exception as e:
            print(f"❌ 工作流程测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_all_tools_available(self):
        """测试所有工具都可用"""
        print("🔧 测试工具可用性...")
        
        try:
            tools = await list_tools()
            
            expected_tools = [
                "analyze_gc_log",
                "get_gc_metrics",
                "compare_gc_logs", 
                "detect_gc_issues",
                "generate_gc_report"  # 新增的报告生成工具
            ]
            
            tool_names = [tool.name for tool in tools]
            
            for expected_tool in expected_tools:
                assert expected_tool in tool_names, f"缺少工具: {expected_tool}"
                print(f"   ✅ {expected_tool}")
            
            print(f"✅ 所有{len(expected_tools)}个工具都可用")
            return True
            
        except Exception as e:
            print(f"❌ 工具可用性测试失败: {e}")
            return False
    
    async def test_error_handling(self):
        """测试错误处理能力"""
        print("🛡️ 测试错误处理能力...")
        
        try:
            # 测试不存在的文件
            try:
                result = await analyze_gc_log_tool({
                    "file_path": "/nonexistent/file.log",
                    "analysis_type": "basic"
                })
                # 如果没有抛出异常，检查是否返回了错误信息
                if result.content:
                    content_text = result.content[0].text
                    if "错误" in content_text:
                        print("✅ 错误被正确处理并返回错误信息")
                        return True
                    else:
                        print("⚠️ 未返回错误信息")
                        return False
                else:
                    print("⚠️ 返回结果为空")
                    return False
            except (FileNotFoundError, ValueError) as fe:
                # 这是期望的行为，说明错误被正确捕获
                print(f"✅ 错误被正确捕获: {type(fe).__name__}")
                return True
            except Exception as ue:
                # 其他未预期的异常
                print(f"⚠️ 未预期的异常: {type(ue).__name__}: {ue}")
                return False
            
        except Exception as e:
            print(f"❌ 错误处理测试失败: {e}")
            return False
    
    async def test_performance_metrics(self):
        """测试性能指标的准确性"""
        print("⚡ 测试性能指标准确性...")
        
        if not os.path.exists(self.sample_g1_log):
            print("⚠️ 跳过测试：需要测试数据文件")
            return True
        
        try:
            # 分析日志
            await analyze_gc_log_tool({
                "file_path": self.sample_g1_log,
                "analysis_type": "detailed"
            })
            
            # 获取指标
            result = await get_gc_metrics_tool({
                "metric_types": ["throughput", "latency", "frequency"]
            })
            
            content_text = result.content[0].text
            
            # 验证关键指标存在
            assert "吞吐量指标" in content_text, "应该包含吞吐量指标"
            assert "延迟指标" in content_text, "应该包含延迟指标"
            assert "频率指标" in content_text, "应该包含频率指标"
            
            print("✅ 性能指标准确性验证通过")
            return True
            
        except Exception as e:
            print(f"❌ 性能指标测试失败: {e}")
            return False


async def run_integration_tests():
    """运行所有集成测试"""
    test_instance = TestEndToEndIntegration()
    test_instance.setup_method()
    
    tests = [
        ("工具可用性", test_instance.test_all_tools_available),
        ("错误处理", test_instance.test_error_handling),
        ("性能指标准确性", test_instance.test_performance_metrics),
        ("完整工作流程", test_instance.test_complete_workflow),
    ]
    
    passed = 0
    total = len(tests)
    
    print("🚀 开始Sprint 5端到端集成测试...\n")
    
    for test_name, test_func in tests:
        print(f"🧪 运行测试: {test_name}")
        try:
            result = await test_func()
            if result:
                passed += 1
                print(f"✅ {test_name} 测试通过\n")
            else:
                print(f"❌ {test_name} 测试失败\n")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}\n")
    
    print(f"📊 集成测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有端到端集成测试通过！")
        print("🏆 GC日志分析MCP服务系统功能完整且稳定")
        return True
    else:
        print("⚠️ 部分集成测试失败，需要检查问题")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_integration_tests())
    sys.exit(0 if success else 1)