"""
NexusAgent Quick Start Example

This script demonstrates how to use NexusAgent for HarmonyOS development.
"""

import asyncio
from pathlib import Path
from coordinator.core.coordinator import MultiAgentCoordinator
from openai import OpenAI
import os


async def main():
    """Main entry point for NexusAgent demo."""
    
    # Configuration
    API_KEY = os.getenv("SILICONFLOW_API_KEY", "your_api_key_here")
    PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", "./sample_project"))
    
    print("🚀 NexusAgent - HarmonyOS Development Assistant")
    print("=" * 60)
    
    # Initialize LLM client
    print("\n📝 Initializing LLM client...")
    llm_client = OpenAI(
        base_url="https://api.siliconflow.cn/v1",
        api_key=API_KEY
    )
    
    # Create coordinator using async factory method (safe in async context)
    print("🏗️  Creating Multi-Agent Coordinator...")
    coordinator = await MultiAgentCoordinator.create(
        llm_client=llm_client,
        llm_model="Pro/zai-org/GLM-5",
        project_root=PROJECT_ROOT
    )
    
    # Define requirement
    requirement = "开发一个登录页面，包含用户名和密码输入框，以及登录按钮"
    
    print(f"\n📋 Requirement: {requirement}")
    print("⏳ Starting workflow...")
    
    # Run workflow
    try:
        result = await coordinator.run_workflow(requirement)
        
        print("\n📊 Workflow Results:")
        print("=" * 60)
        
        for agent_name, agent_result in result["agent_results"].items():
            if agent_result.get("skipped"):
                status = "⏭️"
            elif agent_result.get("success"):
                status = "✅"
            else:
                status = "❌"
            print(f"{status} {agent_name}")
            
            if agent_result.get("skipped"):
                reason = agent_result.get("reason", "Unknown reason")
                print(f"   └─ Skipped: {reason}")
            elif not agent_result.get("success"):
                error = agent_result.get("error", "Unknown error")
                print(f"   └─ Error: {error}")
        
        print("\n" + "=" * 60)
        if result["success"]:
            print("🎉 All tasks completed successfully!")
        else:
            print("⚠️  Some tasks completed with errors:")
            for error in result.get("errors", []):
                print(f"   - {error}")
        
        # Export execution history
        print("\n💾 Exporting execution history...")
        await coordinator.export_execution_history(Path("execution_log.json"))
        print("   └─ Saved to: execution_log.json")
        
        # Show tool observation summary
        print("\n🔧 Tool Execution Summary:")
        observations = await coordinator.blackboard.get("tool_observations", [])
        print(f"   └─ Total tool calls: {len(observations)}")
        
        if observations:
            print("\n   Recent tool calls:")
            for obs in observations[-5:]:
                print(f"      - {obs['agent']}: {obs['tool']} ({obs['result']['status']})")
    
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()


async def demo_tools():
    """Demonstrate individual tool capabilities."""
    
    from coordinator.core.tools import (
        ShellExecutorTool,
        FileManagerTool,
        FileBrowserTool,
        RequirementDecomposerTool
    )
    
    print("\n" + "=" * 60)
    print("🔧 Tool System Demonstration")
    print("=" * 60)
    
    # 1. Shell Executor
    print("\n💻 ShellExecutorTool:")
    shell = ShellExecutorTool()
    result = await shell.execute(command="echo Hello from NexusAgent!")
    if result.status == "success":
        print(f"   ✅ Command output: {result.output['stdout'].strip()}")
    
    # 2. File Manager
    print("\n📁 FileManagerTool:")
    files = FileManagerTool()
    result = await files.execute(
        action="write",
        filepath="demo.txt",
        content="Demo content from NexusAgent!",
        create_dirs=True
    )
    if result.status == "success":
        print(f"   ✅ {result.output}")
    
    # 3. File Browser
    print("\n🔍 FileBrowserTool:")
    browser = FileBrowserTool()
    result = await browser.execute(
        action="list",
        path="coordinator",
        recursive=False
    )
    if result.status == "success":
        print(f"   ✅ Found {len(result.output)} items")
    
    # 4. Requirement Decomposer
    print("\n📝 RequirementDecomposerTool:")
    decomposer = RequirementDecomposerTool()
    result = await decomposer.execute(
        requirement="开发一个登录页面",
        enhanced_analysis=True
    )
    if result.status == "success":
        output = result.output
        print(f"   ✅ Problem type: {output.get('problem_type')}")
        print(f"   ✅ UI components: {len(output.get('ui_components', []))}")
        print(f"   ✅ Technical keywords: {', '.join(output.get('technical_keywords', [])[:3])}...")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--demo-tools":
        # Run tool demonstration only
        asyncio.run(demo_tools())
    else:
        # Run full workflow
        asyncio.run(main())
