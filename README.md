# NexusAgent

基于AI的黑板架构多智能体系统，用于鸿蒙（HarmonyOS）和仓颉（Cangjie）语言的自动化开发。

## 快速开始

```bash
git clone <repository-url>
cd NexusAgent
pip install -r requirements.txt
python test_system.py  # 验证系统
```

## 核心功能

- **4个专业Agent**: 架构师、知识专家、工程师、DevOps
- **智能工具系统**: 命令执行、文件管理、文件浏览、需求分析
- **AI驱动的智能决策**: Agent根据当前上下文，通过LLM判断是否执行每个子步骤（按需执行）
- **决策路径追踪**: 每个智能决策都会记录，可追溯完整的推理过程
- **完整审计追踪**: 每个操作都有记录

## 核心特性

### 按需智能决策（On-Demand Intelligence）

与传统多Agent系统不同的是，NexusAgent的每个Agent都会**根据当前项目的具体需求，智能判断是否执行某个步骤**：

**KnowledgeExpertAgent示例**:
- ❌ 传统做法：总是执行 L1→L2→L3 三个搜索步骤
- ✅ NexusAgent做法：
  1. 执行 L1 搜索
  2. **AI判断**：L1结果是否足够？
     - 如果够 → 直接返回，跳过 L2 和 L3（节省时间）
     - 如果不够 → 执行 L2，再次判断
  3. **AI判断**：L1+L2组合是否足够？
     - 如果够 → 直接返回，跳过 L3
     - 如果不够 → 执行 L3

**DevOpsQAAgent示例**:
- 构建失败时，**AI判断**错误是否可修复
- 如果是简单错误（语法错误）→ 直接尝试修复
- 如果是复杂错误（架构问题）→ 立即创建InternalQuery求助知识专家

## 使用示例

```python
from coordinator.core.coordinator import MultiAgentCoordinator
from openai import OpenAI

llm_client = OpenAI(
    base_url="https://api.siliconflow.cn/v1",
    api_key="your_api_key"
)

coordinator = MultiAgentCoordinator(llm_client=llm_client)
result = await coordinator.run_workflow("开发登录页面")

print(result["success"])  # True if completed successfully
```

## 系统架构

```
协调器 (Coordinator)
    │
    ├─→ 黑板 (Blackboard) ← Agent状态共享
    │
    ├─→ Agent 1: 架构师 (需求分析)
    │   └─→ 智能判断：需求是否有效？
    │
    ├─→ Agent 2: 知识专家 (知识检索) ★★★
    │   ├─→ L1搜索 → AI判断：是否足够？
    │   ├─→ L2搜索(可选) → AI判断：L1+L2是否足够？
    │   └─→ L3搜索(可选)
    │
    ├─→ Agent 3: 工程师 (代码生成)
    └─→ Agent 4: DevOps (构建测试) ★★★
        ├─→ 构建失败 → AI判断：错误是否可修复？
        ├─→ 可修复 → 尝试直接修复
        └─→ 不可修复 → 创建InternalQuery求助

★★★ = AI驱动智能决策节点
```

## 项目文件

```
coordinator/
├── agents/      # 4个Agent
├── core/         # 核心组件（黑板、工具、协调器）
├── tools/        # 4个工具
    ├── shell_executor.py     # 命令执行
    ├── file_manager.py       # 文件管理
    ├── file_browser.py       # 文件浏览
    └── requirement_decomposer.py # 需求分析
└── graph/        # 图搜索集成

tests/           # 测试
test_system.py   # 系统测试
quick_start.py   # 快速开始示例
README.md        # 本文件
requirements.txt # 依赖
LICENSE          # MIT协议
```

## 环境要求

- Python 3.9+
- OpenAI兼容的API（推荐SiliconFlow）

## 文档

- `README.md` - 项目说明（本文件）
- `teaching_manual.md` - 详细教导手册，包含面试准备指南
- `QUICKSTART.md` - 快速开始指南(可选)

## 关键设计理念

### 1. AI判断 vs. 规则匹配

我们选择让**AI来判断**每个步骤是否需要执行，而不是写死规则：

**原因**:
- 不同项目需要不同的组件（这个项目要Button，那个项目要Text）
- 错误的类型千差万别（不能写死只识别"architecture"这个词）
- AI能理解**上下文**，而规则只能匹配关键词

**示例**:
```python
# ❌ 写死规则（假智能）
if len(l1_skills) >= 3 and has_core_keyword:
    return True  # 阈值写死，换项目就不准了

# ✅ AI判断（真智能）
prompt = f"""
当前项目需求: {user_requirement}
找到的L1技能: {l1_skills}

请判断：这些技能是否足够实现这个项目？
- 如果项目需要Button，而L1有Button → 足够
- 如果项目需要复杂的API交互，而L1只有基础语法 → 不够
"""
# AI根据具体项目需求判断
```

### 2. 决策路径追踪

每个Agent执行时都会记录完整的决策路径：

```json
{
  "agent": "KnowledgeExpertAgent",
  "decision_path": [
    "Step 1: L1搜索 → 完成",
    "Step 2: AI判断 → L1不够（缺少WebAPI相关技能）",
    "Step 3: L2搜索 → 完成",
    "Step 4: AI判断 → L1+L2足够（找到了相关API文档）",
    "Step 5: 跳过L3搜索 → 决策完成"
  ],
  "decision_summary": "AI基于项目需求判断，仅执行了L1+L2，跳过了L3"
}
```

好处：
- **可追溯**: 知道为什么执行/跳过某一步
- **可调试**: AI判断错了可以看它为什么会这么判断
- **可优化**: 收集决策数据，改进prompt

### 3. 为什么不只是"更快的规则"？

规则匹配的问题:
- ❌ 需要人工维护规则（新项目改规则）
- ❌ 无法理解上下文（Button和Text在不同项目重要性不同）
- ❌ 边缘情况处理差（新类型的错误从未见过）

AI判断的优势:
- ✅ 适应任何项目（理解需求上下文）
- ✅ 处理未知情况（靠通用判断能力）
- ✅ 减少维护成本（不需要不断写新规则）

## 性能优化

通过按需智能决策，系统避免了不必要的计算：

**传统方式**: 每次都执行完整流程
```
L1搜索 (100ms) → L2搜索 (500ms) → L3搜索 (200ms) = 800ms
```

**NexusAgent方式**: 智能跳过
```
L1搜索 (100ms) → AI判断 (200ms) → 足够！ → 结束 = 300ms
```

**实际收益**: 
- 简单项目节省 **62.5%** 时间（跳过了L2+L3）
- 复杂项目继续执行L2+L3，不遗漏

## 许可证

MIT License - 开源协议
