# NexusAgent

基于黑板架构的多智能体协作系统，专门用于自动化执行鸿蒙（HarmonyOS）应用开发任务。

## 特性

- **多智能体协作**: 4个专业Agent分工协作
  - ArchitectAgent: 需求分析与技术设计
  - KnowledgeExpertAgent: 知识检索与推理
  - CangjieEngineerAgent: 代码生成与依赖配置
  - DevOpsQAAgent: 构建、测试与迭代

- **智能知识检索**: 基于意图路由的GraphDistill图谱搜索
- **引用追溯**: 完整的证据链条用于交叉验证
- **协作式错误修复**: 阶梯式协商解决构建错误
- **知识自动进化**: 对话流程自动累积到Evolution.md

## 技术栈

- Python 3.9+
- asyncio异步编程
- NetworkX图处理
- OpenAI API 兼容接口
- LangChain
- ChromaDB
- Pydantic数据验证

## 架构设计

项目采用黑板模式（Blackboard Pattern）：

```
用户层
    ↓
MultiAgentCoordinator (协调层)
    ↓
GlobalState (黑板 / 共享状态)
    ↓
┌───┐  ┌───┐  ┌───┐  ┌───┐
│ 0 │  │1-3│  │ 4 │  │5-6│
└───┘  └───┘  └───┘  └───┘
```

## 安装

```bash
git clone https://github.com/zhenzhizhi12/NexusAgent.git
cd NexusAgent

pip install -r requirements.txt
```

## 使用

```python
from coordinator.core.coordinator import MultiAgentCoordinator

from openai import OpenAI

llm_client = OpenAI(
    base_url="https://api.siliconflow.cn/v1",
    api_key="your_api_key"
)

coordinator = MultiAgentCoordinator(
    llm_client=llm_client,
    llm_model="Pro/zai-org/GLM-5"
)

result = coordinator.run("开发一个鸿蒙应用")
```

## 目录结构

```
NexusAgent/
├── coordinator/           # 核心协调器
│   ├── agents/           # Agent实现
│   └── core/             # 共享黑板与内部查询
├── graph/                # GraphDistill图谱搜索
├── tests/                # 测试用例
├── .opencode/            # OpenCode相关配置
└── TECHNICAL_DOCUMENTATION.md  # 详细技术文档
```

## 许可证

MIT License
