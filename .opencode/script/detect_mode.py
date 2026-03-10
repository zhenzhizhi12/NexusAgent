#!/usr/bin/env python3
"""
OpenCode 模式检测器

根据任务内容自动选择使用的工作流模式：
1. generic - 通用模式（任意类型软件开发任务）
2. cangjie-common - 仓颉普通工程模式（纯仓颉项目或命令行程序）
3. harmonyos-cangjie - 鸿蒙应用模式（HarmonyOS + 仓颉应用开发）
"""

import json
import sys
import os


class ModeDetector:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '.opencode',
                'platform-config.json'
            )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def detect_mode(self, task_content):
        """
        检测任务应该使用的工作流模式
        
        Args:
            task_content: 任务内容字符串
            
        Returns:
            推荐的模式名称
        """
        task_lower = task_content.lower()
        
        # 检测鸿蒙应用开发关键词
        harmonyos_keywords = [
            'arkui', 'hap', 'module.json5', '鸿蒙页面', '鸿蒙组件',
            'harmonyos', 'ets', 'ability', '鸿蒙', '鸿蒙应用'
        ]
        
        if any(keyword in task_lower for keyword in harmonyos_keywords):
            return 'harmonyos-cangjie'
        
        # 检测仓颉编程关键词
        cangjie_keywords = [
            '仓颉', 'cangjie', 'cjpm', '.cj', '仓颉语言'
        ]
        
        if any(keyword in task_lower for keyword in cangjie_keywords):
            return 'cangjie-common'
        
        # 默认使用通用模式
        return 'generic'
    
    def get_mode_info(self, mode_name):
        """
        获取指定模式的详细信息
        
        Args:
            mode_name: 模式名称
            
        Returns:
            模式配置字典，如果模式不存在则返回 None
        """
        return self.config.get('modes', {}).get(mode_name)
    
    def get_workflow_steps(self, mode_name):
        """
        获取指定模式的工作流步骤
        
        Args:
            mode_name: 模式名称
            
        Returns:
            工作流步骤列表
        """
        mode_info = self.get_mode_info(mode_name)
        if mode_info:
            return mode_info.get('workflow', [])
        return []


def main():
    if len(sys.argv) < 2:
        print("用法: python detect_mode.py <任务内容>")
        print("示例: python detect_mode.py \"开发一个使用仓颉语言的HTTP服务器\"")
        sys.exit(1)
    
    task_content = " ".join(sys.argv[1:])
    detector = ModeDetector()
    
    mode = detector.detect_mode(task_content)
    mode_info = detector.get_mode_info(mode)
    
    print(f"检测到模式: {mode}")
    print(f"模式名称: {mode_info.get('name', 'N/A')}")
    print(f"模式描述: {mode_info.get('description', 'N/A')}")
    print(f"\n工作流步骤:")
    for step in detector.get_workflow_steps(mode):
        print(f"  - {step}")


if __name__ == '__main__':
    main()
