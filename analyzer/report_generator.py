#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC分析报告生成器
支持生成HTML和Markdown格式的专业GC性能分析报告
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional


class GCReportGenerator:
    """GC分析报告生成器"""
    
    def __init__(self):
        """初始化报告生成器"""
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        
    def generate_markdown_report(
        self,
        analysis_data: Dict[str, Any],
        metrics_data: Dict[str, Any],
        alerts_data: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """生成Markdown格式报告"""
        
        report_lines = []
        
        # 报告标题
        report_lines.append("# GC性能分析报告")
        report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 基本信息
        if analysis_data:
            report_lines.append("## 📊 基本信息")
            report_lines.append(f"- **日志类型**: {analysis_data.get('gc_type', 'Unknown')}")
            report_lines.append(f"- **文件路径**: `{analysis_data.get('file_path', 'Unknown')}`")
            report_lines.append(f"- **解析事件数**: {analysis_data.get('total_events', 0)}")
            report_lines.append("")
        
        # 性能指标
        if metrics_data:
            report_lines.append("## 📈 关键性能指标")
            
            # 吞吐量指标
            if 'throughput' in metrics_data:
                throughput = metrics_data['throughput']
                report_lines.append("### 🚀 吞吐量指标")
                report_lines.append(f"- **应用程序时间比例**: {throughput.get('app_time_percentage', 0):.2f}%")
                report_lines.append(f"- **GC时间比例**: {throughput.get('gc_time_percentage', 0):.2f}%")
                report_lines.append("")
            
            # 延迟指标
            if 'latency' in metrics_data:
                latency = metrics_data['latency']
                report_lines.append("### ⏱️ 延迟指标")
                report_lines.append(f"- **平均GC暂停时间**: {latency.get('avg_pause_time', 0):.2f}ms")
                report_lines.append(f"- **最大GC暂停时间**: {latency.get('max_pause_time', 0):.2f}ms")
                report_lines.append(f"- **P99延迟**: {latency.get('p99_pause_time', 0):.2f}ms")
                report_lines.append("")
            
            # 频率指标
            if 'frequency' in metrics_data:
                frequency = metrics_data['frequency']
                report_lines.append("### 🔄 频率指标")
                report_lines.append(f"- **GC频率**: {frequency.get('gc_frequency', 0):.2f} 次/秒")
                report_lines.append(f"- **平均GC间隔**: {frequency.get('avg_interval', 0):.2f}秒")
                report_lines.append("")
        
        # 警报信息
        if alerts_data:
            report_lines.append("## ⚠️ 性能警报")
            
            # 按严重程度分组
            critical_alerts = [a for a in alerts_data if a.get('severity') == 'critical']
            warning_alerts = [a for a in alerts_data if a.get('severity') == 'warning']
            info_alerts = [a for a in alerts_data if a.get('severity') == 'info']
            
            if critical_alerts:
                report_lines.append("### 🚨 严重警报")
                for alert in critical_alerts:
                    report_lines.append(f"- **{alert.get('message', '')}**")
                    if 'details' in alert:
                        report_lines.append(f"  - 详情: {alert['details']}")
                report_lines.append("")
            
            if warning_alerts:
                report_lines.append("### ⚡ 警告")
                for alert in warning_alerts:
                    report_lines.append(f"- {alert.get('message', '')}")
                report_lines.append("")
            
            if info_alerts:
                report_lines.append("### ℹ️ 信息")
                for alert in info_alerts:
                    report_lines.append(f"- {alert.get('message', '')}")
                report_lines.append("")
        
        # 建议
        report_lines.append("## 💡 优化建议")
        suggestions = self._generate_suggestions(metrics_data, alerts_data)
        for suggestion in suggestions:
            report_lines.append(f"- {suggestion}")
        report_lines.append("")
        
        return "\n".join(report_lines)
    
    def generate_html_report(
        self,
        analysis_data: Dict[str, Any],
        metrics_data: Dict[str, Any],
        alerts_data: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """生成HTML格式报告"""
        
        # HTML模板
        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GC性能分析报告</title>
    <style>
        body {{ font-family: 'Arial', sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric-card {{ background: #ecf0f1; padding: 15px; border-radius: 6px; border-left: 4px solid #3498db; }}
        .alert-critical {{ background: #e74c3c; color: white; padding: 10px; border-radius: 4px; margin: 5px 0; }}
        .alert-warning {{ background: #f39c12; color: white; padding: 10px; border-radius: 4px; margin: 5px 0; }}
        .alert-info {{ background: #3498db; color: white; padding: 10px; border-radius: 4px; margin: 5px 0; }}
        .suggestion {{ background: #2ecc71; color: white; padding: 8px; border-radius: 4px; margin: 5px 0; }}
        code {{ background: #ecf0f1; padding: 2px 4px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 GC性能分析报告</h1>
        <p><strong>生成时间:</strong> {timestamp}</p>
        
        {basic_info}
        
        {metrics_section}
        
        {alerts_section}
        
        {suggestions_section}
    </div>
</body>
</html>
        """
        
        # 生成各个部分的HTML
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        basic_info = self._generate_basic_info_html(analysis_data)
        metrics_section = self._generate_metrics_html(metrics_data)
        alerts_section = self._generate_alerts_html(alerts_data)
        suggestions_section = self._generate_suggestions_html(metrics_data, alerts_data)
        
        return html_template.format(
            timestamp=timestamp,
            basic_info=basic_info,
            metrics_section=metrics_section,
            alerts_section=alerts_section,
            suggestions_section=suggestions_section
        )
    
    def _generate_basic_info_html(self, analysis_data: Dict[str, Any]) -> str:
        """生成基本信息HTML部分"""
        if not analysis_data:
            return ""
        
        return f"""
        <h2>📊 基本信息</h2>
        <div class="metric-card">
            <p><strong>日志类型:</strong> {analysis_data.get('gc_type', 'Unknown')}</p>
            <p><strong>文件路径:</strong> <code>{analysis_data.get('file_path', 'Unknown')}</code></p>
            <p><strong>解析事件数:</strong> {analysis_data.get('total_events', 0)}</p>
        </div>
        """
    
    def _generate_metrics_html(self, metrics_data: Dict[str, Any]) -> str:
        """生成指标HTML部分"""
        if not metrics_data:
            return ""
        
        html_parts = ['<h2>📈 关键性能指标</h2>', '<div class="metric-grid">']
        
        # 吞吐量指标
        if 'throughput' in metrics_data:
            throughput = metrics_data['throughput']
            html_parts.append(f"""
            <div class="metric-card">
                <h3>🚀 吞吐量指标</h3>
                <p>应用程序时间比例: <strong>{throughput.get('app_time_percentage', 0):.2f}%</strong></p>
                <p>GC时间比例: <strong>{throughput.get('gc_time_percentage', 0):.2f}%</strong></p>
            </div>
            """)
        
        # 延迟指标
        if 'latency' in metrics_data:
            latency = metrics_data['latency']
            html_parts.append(f"""
            <div class="metric-card">
                <h3>⏱️ 延迟指标</h3>
                <p>平均暂停时间: <strong>{latency.get('avg_pause_time', 0):.2f}ms</strong></p>
                <p>最大暂停时间: <strong>{latency.get('max_pause_time', 0):.2f}ms</strong></p>
                <p>P99延迟: <strong>{latency.get('p99_pause_time', 0):.2f}ms</strong></p>
            </div>
            """)
        
        html_parts.append('</div>')
        return ''.join(html_parts)
    
    def _generate_alerts_html(self, alerts_data: List[Dict[str, Any]]) -> str:
        """生成警报HTML部分"""
        if not alerts_data:
            return ""
        
        html_parts = ['<h2>⚠️ 性能警报</h2>']
        
        # 按严重程度分组
        critical_alerts = [a for a in alerts_data if a.get('severity') == 'critical']
        warning_alerts = [a for a in alerts_data if a.get('severity') == 'warning']
        info_alerts = [a for a in alerts_data if a.get('severity') == 'info']
        
        if critical_alerts:
            html_parts.append('<h3>🚨 严重警报</h3>')
            for alert in critical_alerts:
                html_parts.append(f'<div class="alert-critical">{alert.get("message", "")}</div>')
        
        if warning_alerts:
            html_parts.append('<h3>⚡ 警告</h3>')
            for alert in warning_alerts:
                html_parts.append(f'<div class="alert-warning">{alert.get("message", "")}</div>')
        
        if info_alerts:
            html_parts.append('<h3>ℹ️ 信息</h3>')
            for alert in info_alerts:
                html_parts.append(f'<div class="alert-info">{alert.get("message", "")}</div>')
        
        return ''.join(html_parts)
    
    def _generate_suggestions_html(self, metrics_data: Dict[str, Any], alerts_data: List[Dict[str, Any]]) -> str:
        """生成建议HTML部分"""
        suggestions = self._generate_suggestions(metrics_data, alerts_data)
        if not suggestions:
            return ""
        
        html_parts = ['<h2>💡 优化建议</h2>']
        for suggestion in suggestions:
            html_parts.append(f'<div class="suggestion">{suggestion}</div>')
        
        return ''.join(html_parts)
    
    def _generate_suggestions(self, metrics_data: Dict[str, Any], alerts_data: List[Dict[str, Any]]) -> List[str]:
        """根据指标和警报生成优化建议"""
        suggestions = []
        
        if not metrics_data:
            return suggestions
        
        # 基于吞吐量的建议
        if 'throughput' in metrics_data:
            throughput = metrics_data['throughput']
            gc_time_percentage = throughput.get('gc_time_percentage', 0)
            
            if gc_time_percentage > 10:
                suggestions.append("GC时间占比过高，建议调整堆大小或GC策略")
            elif gc_time_percentage > 5:
                suggestions.append("GC时间占比较高，可考虑优化应用程序内存使用")
        
        # 基于延迟的建议
        if 'latency' in metrics_data:
            latency = metrics_data['latency']
            max_pause_time = latency.get('max_pause_time', 0)
            p99_pause_time = latency.get('p99_pause_time', 0)
            
            if max_pause_time > 1000:
                suggestions.append("存在超长GC暂停，建议检查老年代GC策略")
            elif p99_pause_time > 200:
                suggestions.append("P99延迟较高，建议优化GC参数设置")
        
        # 基于频率的建议
        if 'frequency' in metrics_data:
            frequency = metrics_data['frequency']
            gc_frequency = frequency.get('gc_frequency', 0)
            
            if gc_frequency > 2:
                suggestions.append("GC频率过高，建议增加堆大小或优化内存分配")
        
        # 基于警报的建议
        if alerts_data:
            critical_count = len([a for a in alerts_data if a.get('severity') == 'CRITICAL'])
            if critical_count > 0:
                suggestions.append(f"检测到{critical_count}个严重性能问题，建议立即处理")
        
        # 默认建议
        if not suggestions:
            suggestions.append("当前GC性能表现良好，建议继续监控关键指标")
        
        return suggestions
    
    def save_report(self, content: str, file_path: str, format_type: str = "markdown") -> bool:
        """保存报告到文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 根据格式类型设置文件扩展名
            if format_type.lower() == "html" and not file_path.endswith('.html'):
                file_path += '.html'
            elif format_type.lower() == "markdown" and not file_path.endswith('.md'):
                file_path += '.md'
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            print(f"保存报告失败: {e}")
            return False


# 便利函数
def generate_gc_report(
    analysis_data: Dict[str, Any],
    metrics_data: Dict[str, Any],
    alerts_data: Optional[List[Dict[str, Any]]] = None,
    format_type: str = "markdown",
    output_file: Optional[str] = None
) -> str:
    """生成GC分析报告的便利函数"""
    
    generator = GCReportGenerator()
    
    if format_type.lower() == "html":
        content = generator.generate_html_report(analysis_data, metrics_data, alerts_data)
    else:
        content = generator.generate_markdown_report(analysis_data, metrics_data, alerts_data)
    
    # 如果指定了输出文件，保存到文件
    if output_file:
        generator.save_report(content, output_file, format_type)
    
    return content


if __name__ == "__main__":
    # 测试代码
    test_analysis = {
        "gc_type": "G1 GC",
        "file_path": "/tmp/test.log",
        "total_events": 150
    }
    
    test_metrics = {
        "throughput": {
            "app_time_percentage": 92.5,
            "gc_time_percentage": 7.5
        },
        "latency": {
            "avg_pause_time": 25.3,
            "max_pause_time": 156.7,
            "p99_pause_time": 89.2
        },
        "frequency": {
            "gc_frequency": 1.2,
            "avg_interval": 0.83
        }
    }
    
    test_alerts = [
        {
            "severity": "WARNING",
            "message": "GC频率较高",
            "details": "每秒1.2次GC"
        }
    ]
    
    # 生成测试报告
    markdown_report = generate_gc_report(test_analysis, test_metrics, test_alerts, "markdown")
    html_report = generate_gc_report(test_analysis, test_metrics, test_alerts, "html")
    
    print("Markdown报告已生成")
    print("HTML报告已生成")