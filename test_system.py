"""
NexusAgent Syntax Check and Test Script

Verify all Python modules can be imported and instantiated correctly.
"""

import sys
from pathlib import Path

def check_imports():
    """Check if all Python modules can be imported."""
    print("Checking module imports...")
    
    modules = [
        "coordinator.core.tool",
        "coordinator.core.blackboard",
        "coordinator.core.coordinator",
        "coordinator.agents.base_agent",
        "coordinator.agents.architect_agent",
        "coordinator.agents.knowledge_agent",
        "coordinator.agents.engineer_agent",
        "coordinator.agents.devops_agent",
    ]
    
    success_count = 0
    total_count = len(modules)
    
    for module_name in modules:
        try:
            __import__(module_name)
            print(f"  [OK] {module_name}")
            success_count += 1
        except Exception as e:
            print(f"  [FAIL] {module_name}: {e}")
    
    print(f"\nImport results: {success_count}/{total_count} passed")
    return success_count == total_count


def check_tool_system():
    """Check if tool system works correctly."""
    print("\nChecking tool system...")
    
    try:
        from coordinator.core.tool import BaseTool, ToolExecutionResult, ToolArgument
        print("  [OK] BaseTool")
        
        from coordinator.core.tools import (
            ShellExecutorTool,
            FileManagerTool,
            FileBrowserTool,
            RequirementDecomposerTool
        )
        print("  [OK] ShellExecutorTool")
        print("  [OK] FileManagerTool")
        print("  [OK] FileBrowserTool")
        print("  [OK] RequirementDecomposerTool")
        
        # Test tool instantiation
        shell = ShellExecutorTool()
        print(f"  [OK] ShellExecutorTool instantiated: {shell.name}")
        
        files = FileManagerTool()
        print(f"  [OK] FileManagerTool instantiated: {files.name}")
        
        browser = FileBrowserTool()
        print(f"  [OK] FileBrowserTool instantiated: {browser.name}")
        
        decomposer = RequirementDecomposerTool()
        print(f"  [OK] RequirementDecomposerTool instantiated: {decomposer.name}")
        
        print("\nTool system check: All passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] Tool system failed: {e}")
        return False


def check_agents():
    """Check if all agents can be initialized normally."""
    print("\nChecking Agent system...")
    
    try:
        from coordinator.core.blackboard import GlobalState
        
        blackboard = GlobalState()
        print("  [OK] GlobalState blackboard initialized")
        
        from coordinator.agents.architect_agent import ArchitectAgent
        architect = ArchitectAgent(blackboard=blackboard)
        print(f"  [OK] ArchitectAgent initialized: {architect.name}")
        
        from coordinator.agents.knowledge_agent import KnowledgeExpertAgent
        knowledge = KnowledgeExpertAgent(blackboard=blackboard)
        print(f"  [OK] KnowledgeExpertAgent initialized: {knowledge.name}")
        
        from coordinator.agents.engineer_agent import CangjieEngineerAgent
        engineer = CangjieEngineerAgent(blackboard=blackboard)
        print(f"  [OK] CangjieEngineerAgent initialized: {engineer.name}")
        
        from coordinator.agents.devops_agent import DevOpsQAAgent
        devops = DevOpsQAAgent(
            blackboard=blackboard,
            build_script_path=Path(".opencode/skills/cangjie-dev-harmonyos/scripts/build.ps1"),
            evolution_path=Path(".opencode/skills/cangjie-dev-harmonyos/Evolution.md")
        )
        print(f"  [OK] DevOpsQAAgent initialized: {devops.name}")
        
        print("\nAgent system check: All passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] Agent system failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_coordinator():
    """Check if coordinator can be initialized normally."""
    print("\nChecking coordinator...")
    
    try:
        from coordinator.core.coordinator import MultiAgentCoordinator
        print("  [OK] MultiAgentCoordinator imported successfully")
        
        print("\nCoordinator check: Passed")
        return True
        
    except Exception as e:
        print(f"  [FAIL] Coordinator failed: {e}")
        return False


def main():
    """Execute all checks."""
    print("=" * 60)
    print("NexusAgent System Test")
    print("=" * 60)
    print()
    
    results = []
    
    # 1. Check module imports
    results.append(("Module Imports", check_imports()))
    
    # 2. Check tool system
    results.append(("Tool System", check_tool_system()))
    
    # 3. Check agent system
    results.append(("Agent System", check_agents()))
    
    # 4. Check coordinator
    results.append(("Coordinator", check_coordinator()))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name}: {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed! System ready!")
        print("=" * 60)
        return 0
    else:
        print("Some tests failed, check error messages")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
