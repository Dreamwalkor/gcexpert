#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC日志分析平台启动脚本
包含新的图表缩放和内存趋势功能
"""

import os
import sys
import subprocess
import signal
import time

def stop_existing_service():
    """停止现有的Web服务"""
    print("🛑 停止现有的Web服务...")
    try:
        # 查找并停止现有的web_frontend.py进程
        result = subprocess.run(['pgrep', '-f', 'python.*web_frontend.py'], 
                              capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"   ✅ 停止进程 {pid}")
                except:
                    pass
            time.sleep(2)  # 等待进程完全停止
        else:
            print("   ℹ️ 没有找到运行中的服务")
    except Exception as e:
        print(f"   ⚠️ 停止服务时出错: {e}")

def start_service():
    """启动Web服务"""
    print("🚀 启动增强版GC日志分析Web服务...")
    print("📊 新功能包括:")
    print("   • 内存区域趋势图 (堆、Eden、Survivor、老年代)")
    print("   • 图表缩放功能 (时间范围选择、鼠标缩放)")
    print("   • 堆利用率分析 (利用率和回收效率)")
    print("   • 同步图表更新")
    print()
    
    try:
        # 启动Web服务
        subprocess.run([sys.executable, 'web_frontend.py'], check=True)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

def main():
    """主函数"""
    print("🔍 GC日志分析平台 - 增强版")
    print("=" * 50)
    
    # 检查必要文件
    required_files = ['web_frontend.py', 'web_optimizer.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ 缺少必要文件: {missing_files}")
        return
    
    # 停止现有服务
    stop_existing_service()
    
    # 启动新服务
    start_service()

if __name__ == "__main__":
    main()