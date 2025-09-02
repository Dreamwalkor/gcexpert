#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint 5: 性能测试与优化
验证GC日志分析系统的性能指标
"""

import os
import sys
import time
import asyncio
from statistics import mean, median

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from main import (
    analyze_gc_log_tool,
    get_gc_metrics_tool,
    detect_gc_issues_tool,
    generate_gc_report_tool
)


class PerformanceTest:
    """性能测试类"""
    
    def __init__(self):
        self.test_data_dir = os.path.join(project_root, 'test', 'data')
        self.sample_g1_log = os.path.join(self.test_data_dir, 'sample_g1.log')
        self.sample_j9_log = os.path.join(self.test_data_dir, 'sample_j9.log')
        self.performance_results = {}
    
    async def measure_function_time(self, func, *args, **kwargs):
        """测量函数执行时间"""
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    
    async def test_analyze_performance(self):
        """测试分析功能的性能"""
        print("⚡ 测试GC日志分析性能...")
        
        if not os.path.exists(self.sample_g1_log):
            print("⚠️ 跳过测试：G1测试数据文件不存在")
            return False
        
        # 多次运行测试获取平均性能
        times = []
        test_count = 5
        
        for i in range(test_count):
            result, exec_time = await self.measure_function_time(
                analyze_gc_log_tool,
                {"file_path": self.sample_g1_log, "analysis_type": "detailed"}
            )
            times.append(exec_time)
            print(f"   运行 {i+1}: {exec_time:.3f}s")
        
        avg_time = mean(times)
        median_time = median(times)
        min_time = min(times)
        max_time = max(times)
        
        self.performance_results['analyze'] = {
            'avg_time': avg_time,
            'median_time': median_time,
            'min_time': min_time,
            'max_time': max_time
        }
        
        print(f"✅ 分析性能统计:")
        print(f"   平均时间: {avg_time:.3f}s")
        print(f"   中位数时间: {median_time:.3f}s")
        print(f"   最快时间: {min_time:.3f}s")
        print(f"   最慢时间: {max_time:.3f}s")
        
        # 性能标准：分析应该在2秒内完成
        if avg_time < 2.0:
            print("🚀 分析性能优秀!")
            return True
        elif avg_time < 5.0:
            print("✅ 分析性能良好")
            return True
        else:
            print("⚠️ 分析性能需要优化")
            return False
    
    async def test_metrics_performance(self):
        """测试指标获取性能"""
        print("📊 测试指标获取性能...")
        
        if not os.path.exists(self.sample_g1_log):
            print("⚠️ 跳过测试：需要先分析日志")
            return True
        
        # 先分析一个日志
        await analyze_gc_log_tool({
            "file_path": self.sample_g1_log,
            "analysis_type": "detailed"
        })
        
        # 测试指标获取性能
        times = []
        test_count = 10
        
        for i in range(test_count):
            result, exec_time = await self.measure_function_time(
                get_gc_metrics_tool,
                {"metric_types": ["all"]}
            )
            times.append(exec_time)
        
        avg_time = mean(times)
        min_time = min(times)
        max_time = max(times)
        
        self.performance_results['metrics'] = {
            'avg_time': avg_time,
            'min_time': min_time,
            'max_time': max_time
        }
        
        print(f"✅ 指标获取性能:")
        print(f"   平均时间: {avg_time:.3f}s")
        print(f"   最快时间: {min_time:.3f}s")
        print(f"   最慢时间: {max_time:.3f}s")
        
        # 指标获取应该非常快（小于0.1秒）
        if avg_time < 0.1:
            print("🚀 指标获取性能优秀!")
            return True
        elif avg_time < 0.5:
            print("✅ 指标获取性能良好")
            return True
        else:
            print("⚠️ 指标获取性能需要优化")
            return False
    
    async def test_report_generation_performance(self):
        """测试报告生成性能"""
        print("📝 测试报告生成性能...")
        
        if not os.path.exists(self.sample_g1_log):
            print("⚠️ 跳过测试：需要先分析日志")
            return True
        
        # 先分析一个日志
        await analyze_gc_log_tool({
            "file_path": self.sample_g1_log,
            "analysis_type": "detailed"
        })
        
        # 测试Markdown报告生成
        md_result, md_time = await self.measure_function_time(
            generate_gc_report_tool,
            {"format_type": "markdown", "include_alerts": True}
        )
        
        # 测试HTML报告生成
        html_result, html_time = await self.measure_function_time(
            generate_gc_report_tool,
            {"format_type": "html", "include_alerts": True}
        )
        
        self.performance_results['reports'] = {
            'markdown_time': md_time,
            'html_time': html_time
        }
        
        print(f"✅ 报告生成性能:")
        print(f"   Markdown报告: {md_time:.3f}s")
        print(f"   HTML报告: {html_time:.3f}s")
        
        # 报告生成应该在1秒内完成
        if md_time < 1.0 and html_time < 1.0:
            print("🚀 报告生成性能优秀!")
            return True
        elif md_time < 2.0 and html_time < 2.0:
            print("✅ 报告生成性能良好")
            return True
        else:
            print("⚠️ 报告生成性能需要优化")
            return False
    
    async def test_memory_usage(self):
        """测试内存使用情况"""
        print("💾 测试内存使用情况...")
        
        try:
            import psutil
            import os
            
            # 获取当前进程
            process = psutil.Process(os.getpid())
            
            # 记录初始内存使用
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            if os.path.exists(self.sample_g1_log):
                # 执行一系列操作
                await analyze_gc_log_tool({
                    "file_path": self.sample_g1_log,
                    "analysis_type": "detailed"
                })
                
                await get_gc_metrics_tool({"metric_types": ["all"]})
                
                await detect_gc_issues_tool({})
                
                await generate_gc_report_tool({
                    "format_type": "markdown",
                    "include_alerts": True
                })
            
            # 记录最终内存使用
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            print(f"✅ 内存使用情况:")
            print(f"   初始内存: {initial_memory:.1f}MB")
            print(f"   最终内存: {final_memory:.1f}MB")
            print(f"   内存增加: {memory_increase:.1f}MB")
            
            # 内存增加应该小于50MB
            if memory_increase < 50:
                print("🚀 内存使用优秀!")
                return True
            elif memory_increase < 100:
                print("✅ 内存使用良好")
                return True
            else:
                print("⚠️ 内存使用需要优化")
                return False
                
        except ImportError:
            print("⚠️ 跳过内存测试：缺少psutil库")
            return True
    
    async def test_concurrent_performance(self):
        """测试并发性能"""
        print("🔄 测试并发处理性能...")
        
        if not os.path.exists(self.sample_g1_log):
            print("⚠️ 跳过测试：需要测试数据文件")
            return True
        
        # 并发执行多个分析任务
        concurrent_count = 3
        
        start_time = time.time()
        
        tasks = []
        for i in range(concurrent_count):
            task = analyze_gc_log_tool({
                "file_path": self.sample_g1_log,
                "analysis_type": "basic"
            })
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # 验证所有任务都成功完成
        success_count = len([r for r in results if r.content])
        
        print(f"✅ 并发性能测试:")
        print(f"   任务数量: {concurrent_count}")
        print(f"   成功完成: {success_count}")
        print(f"   总时间: {total_time:.3f}s")
        print(f"   平均每任务: {total_time/concurrent_count:.3f}s")
        
        if success_count == concurrent_count and total_time < 10.0:
            print("🚀 并发性能优秀!")
            return True
        elif success_count == concurrent_count:
            print("✅ 并发性能良好")
            return True
        else:
            print("⚠️ 并发性能需要优化")
            return False
    
    def generate_performance_report(self):
        """生成性能测试报告"""
        print("\n📊 性能测试报告:")
        print("=" * 50)
        
        if 'analyze' in self.performance_results:
            analyze = self.performance_results['analyze']
            print(f"🔍 日志分析性能:")
            print(f"   平均时间: {analyze['avg_time']:.3f}s")
            print(f"   性能评级: {'优秀' if analyze['avg_time'] < 2.0 else '良好' if analyze['avg_time'] < 5.0 else '需优化'}")
        
        if 'metrics' in self.performance_results:
            metrics = self.performance_results['metrics']
            print(f"📈 指标获取性能:")
            print(f"   平均时间: {metrics['avg_time']:.3f}s")
            print(f"   性能评级: {'优秀' if metrics['avg_time'] < 0.1 else '良好' if metrics['avg_time'] < 0.5 else '需优化'}")
        
        if 'reports' in self.performance_results:
            reports = self.performance_results['reports']
            print(f"📝 报告生成性能:")
            print(f"   Markdown: {reports['markdown_time']:.3f}s")
            print(f"   HTML: {reports['html_time']:.3f}s")
            md_rating = '优秀' if reports['markdown_time'] < 1.0 else '良好' if reports['markdown_time'] < 2.0 else '需优化'
            html_rating = '优秀' if reports['html_time'] < 1.0 else '良好' if reports['html_time'] < 2.0 else '需优化'
            print(f"   性能评级: Markdown-{md_rating}, HTML-{html_rating}")
        
        print("=" * 50)


async def run_performance_tests():
    """运行所有性能测试"""
    perf_test = PerformanceTest()
    
    tests = [
        ("日志分析性能", perf_test.test_analyze_performance),
        ("指标获取性能", perf_test.test_metrics_performance),
        ("报告生成性能", perf_test.test_report_generation_performance),
        ("内存使用测试", perf_test.test_memory_usage),
        ("并发处理性能", perf_test.test_concurrent_performance),
    ]
    
    passed = 0
    total = len(tests)
    
    print("🚀 开始Sprint 5性能测试...\n")
    
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
    
    # 生成性能报告
    perf_test.generate_performance_report()
    
    print(f"\n📊 性能测试结果: {passed}/{total} 通过")
    
    if passed >= total * 0.8:  # 80%通过率即为良好
        print("🎉 系统性能表现良好！")
        return True
    else:
        print("⚠️ 系统性能需要优化")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_performance_tests())
    sys.exit(0 if success else 1)