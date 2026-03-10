#!/usr/bin/env python3
"""
OpenCode 工作流执行器

根据任务内容自动选择并执行对应模式的工作流：
1. generic - 通用模式（任意类型软件开发任务）
2. cangjie-common - 仓颉普通工程模式（纯仓颉项目或命令行程序）
3. harmonyos-cangjie - 鸿蒙应用模式（HarmonyOS + 仓颉应用开发）
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional


class WorkflowExecutor:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'platform-config.json'
            )
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.workspace_root = self.config.get('paths', {}).get('workspace-root', '')
        
        # 导入模式检测器
        sys.path.insert(0, os.path.dirname(__file__))
        from detect_mode import ModeDetector
        self.detector = ModeDetector(config_path)
    
    def detect_mode(self, task_content: str) -> str:
        """检测任务应该使用的工作流模式"""
        return self.detector.detect_mode(task_content)
    
    def get_mode_info(self, mode_name: str) -> Dict[str, Any]:
        """获取指定模式的详细信息"""
        return self.config.get('modes', {}).get(mode_name, {})
    
    def get_workflow_config(self, mode_name: str) -> Dict[str, Any]:
        """获取指定模式的工作流配置"""
        workflow_rules = self.config.get('workflow-rules', {})
        return workflow_rules.get(mode_name, {})
    
    def get_skill_path(self, skill_name: str) -> Optional[str]:
        """获取指定技能的路径"""
        paths = self.config.get('paths', {})
        
        # 检查是否在 paths 中直接定义
        if skill_name in paths:
            return paths[skill_name]
        
        # 检查 common-skill-l1 中的子技能
        for key in paths:
            if key.startswith(skill_name.replace('-', '_')):
                return paths[key]
        
        return None
    
    def read_evolution(self, mode_name: str) -> Optional[str]:
        """读取相应模式的 Evolution.md 文件"""
        paths = self.config.get('paths', {})
        
        if mode_name == 'cangjie-common':
            evolution_file = os.path.join(
                self.workspace_root,
                paths.get('cangjie-evolution', {}).get('evolution-file', '')
            )
        elif mode_name == 'harmonyos-cangjie':
            evolution_file = os.path.join(
                self.workspace_root,
                paths.get('harmonyos-evolution', {}).get('evolution-file', '')
            )
        else:
            return None
        
        if os.path.exists(evolution_file):
            with open(evolution_file, 'r', encoding='utf-8') as f:
                return f.read()
        return None
    
    def record_evolution(self, mode_name: str, content: str):
        """将内容记录到相应模式的 Evolution.md 文件"""
        paths = self.config.get('paths', {})
        
        if mode_name == 'cangjie-common':
            evolution_file = os.path.join(
                self.workspace_root,
                paths.get('cangjie-evolution', {}).get('evolution-file', '')
            )
        elif mode_name == 'harmonyos-cangjie':
            evolution_file = os.path.join(
                self.workspace_root,
                paths.get('harmonyos-evolution', {}).get('evolution-file', '')
            )
        else:
            print(f"模式 {mode_name} 不支持 Evolution 记录")
            return
        
        with open(evolution_file, 'a', encoding='utf-8') as f:
            f.write(content)
        
        print(f"已记录到 Evolution.md: {evolution_file}")
    
    def generate_workflow_instructions(self, mode_name: str) -> str:
        """生成指定模式的完整工作流指令"""
        mode_info = self.get_mode_info(mode_name)
        workflow_config = self.get_workflow_config(mode_name)
        
        if not mode_info or not workflow_config:
            return f"错误: 模式 {mode_name} 配置不存在"
        
        instructions = f"# {mode_info.get('name', 'N/A')} 工作流\n\n"
        instructions += f"**描述**: {mode_info.get('description', 'N/A')}\n\n"
        instructions += f"**编程语言**: {mode_info.get('language', 'N/A')}\n\n"
        instructions += f"**核心技能**:\n"
        for skill in mode_info.get('skills', []):
            instructions += f"  - {skill}\n"
        
        instructions += "\n## 工作流步骤\n\n"
        
        for step in mode_info.get('workflow', []):
            if step in workflow_config:
                step_config = workflow_config[step]
                instructions += f"### {step_config.get('description', step)}\n\n"
                
                if 'skill' in step_config:
                    instructions += f"**使用技能**: {step_config['skill']}\n\n"
                
                if 'file' in step_config:
                    instructions += f"**相关文件**: {step_config['file']}\n\n"
                
                if 'script' in step_config:
                    instructions += f"**脚本路径**: {step_config['script']}\n\n"
                
                if 'docs-path' in step_config:
                    instructions += f"**文档路径**: {step_config['docs-path']}\n\n"
                
                if 'error-handling' in step_config:
                    instructions += f"**错误处理流程**:\n"
                    for err_step in step_config['error-handling']:
                        instructions += f"  1. {err_step}\n"
                    instructions += "\n"
                
                if 'required' in step_config:
                    if step_config['required']:
                        instructions += "**必需步骤**: 是\n\n"
        
        return instructions
    
    def get_public_principles(self) -> str:
        """获取公共原则"""
        principles = self.config.get('workflow-rules', {}).get('public-principles', [])
        
        result = "# 公共原则\n\n"
        for principle in principles:
            result += f"- {principle}\n"
        
        return result
    
    def get_stdx_config_template(self, mode_name: str) -> Optional[str]:
        """获取 stdx 配置模板"""
        workflow_config = self.get_workflow_config(mode_name)
        
        if 'stdx-config' in workflow_config:
            stdx_config = workflow_config['stdx-config']
            
            if 'config-template' in stdx_config:
                return stdx_config['config-template']
            
            if 'windows-path-format' in stdx_config:
                return stdx_config['windows-path-format']['config-template']
        
        return None


def main():
    parser = WorkflowExecutor()
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python workflow_executor.py <任务内容> - 检测模式并生成工作流指令")
        print("  python workflow_executor.py --mode <模式名> - 显示指定模式的工作流指令")
        print("  python workflow_executor.py --principles - 显示公共原则")
        print("  python workflow_executor.py --stdx-config <模式名> - 显示 stdx 配置模板")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == '--mode':
        if len(sys.argv) < 3:
            print("错误: 需要指定模式名")
            sys.exit(1)
        
        mode = sys.argv[2]
        instructions = parser.generate_workflow_instructions(mode)
        print(instructions)
    
    elif action == '--principles':
        principles = parser.get_public_principles()
        print(principles)
    
    elif action == '--stdx-config':
        if len(sys.argv) < 3:
            print("错误: 需要指定模式名")
            sys.exit(1)
        
        mode = sys.argv[2]
        template = parser.get_stdx_config_template(mode)
        if template:
            print(template)
        else:
            print(f"错误: 模式 {mode} 没有 stdx 配置模板")
    
    else:
        # 检测模式并生成工作流指令
        task_content = " ".join(sys.argv[1:])
        mode = parser.detect_mode(task_content)
        
        print(f"# 检测到模式: {mode}\n")
        print(parser.get_public_principles())
        print("\n")
        print(parser.generate_workflow_instructions(mode))


if __name__ == '__main__':
    main()
