from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from git import Repo
from openai import OpenAI

from .extractor import extract_graph_from_text
from graph_builder import GraphBuilder


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("graphdistill.main")


# ---------------------------------------------------------------------------
# 1. 核心配置定义 (数据源“采矿地图” + LLM 接口配置)
# ---------------------------------------------------------------------------

BASE_URL = "https://api.siliconflow.cn/v1"
MODEL = "Pro/zai-org/GLM-5"

DOC_PRESETS: Dict[str, Dict[str, str]] = {
    "Cangjie_Guide": {
        "url": "https://gitcode.com/Cangjie/cangjie_docs.git",
        "branch": "release/1.0",
        "subdir": "docs/dev-guide",
    },
    "Cangjie_Tools": {
        "url": "https://gitcode.com/Cangjie/cangjie_docs.git",
        "branch": "release/1.0",
        "subdir": "docs/tools",
    },
    "Cangjie_StdLib": {
        "url": "https://gitcode.com/Cangjie/cangjie_runtime.git",
        "branch": "release/1.0",
        "subdir": "std/doc/libs",
    },
    "Cangjie_StdX": {
        "url": "https://gitcode.com/Cangjie/cangjie_stdx.git",
        "branch": "release/1.0",
        "subdir": "doc",
    },
    "HarmonyOS_Cangjie": {
        "url": "https://gitcode.com/openharmony-sig/docs_cangjie.git",
        "branch": "master",
        "subdir": "zh-cn/application-dev",
    },
}

TEMP_REPOS_DIR = Path("temp_repos")
GRAPH_JSON_PATH = Path("test_graph_1.json")


def ensure_repos_dir() -> None:
    TEMP_REPOS_DIR.mkdir(parents=True, exist_ok=True)


def clone_or_get_repo(name: str, cfg: Dict[str, str]) -> Path:
    """
    确保指定预设仓库已被克隆到本地。

    优化：如果多个预设指向同一个 URL + branch，会复用已存在的仓库，避免重复克隆。
    若仓库不存在则执行 clone_from；若已存在则直接复用（暂不强制 pull，以保证可重复性）。
    """
    ensure_repos_dir()
    url = cfg["url"]
    branch = cfg["branch"]
    
    # 检查是否已经有相同 URL 的仓库（避免重复克隆）
    # 遍历已存在的目录，检查 git remote URL
    for existing_dir in TEMP_REPOS_DIR.iterdir():
        if not existing_dir.is_dir():
            continue
        git_dir = existing_dir / ".git"
        if git_dir.exists():
            try:
                existing_repo = Repo(existing_dir)
                existing_urls = list(existing_repo.remotes.origin.urls)
                existing_url = existing_urls[0] if existing_urls else None
                
                # 如果 URL 匹配，复用这个仓库（即使 branch 不同，也可以 checkout）
                if existing_url == url:
                    logger.info(
                        "Reusing existing repo for %s: %s (requested branch=%s) at %s",
                        name,
                        url,
                        branch,
                        existing_dir,
                    )
                    # 如果需要不同的 branch，尝试 checkout（可选，不影响主要功能）
                    if branch:
                        try:
                            existing_repo.git.checkout(branch)
                        except Exception:  # noqa: BLE001
                            logger.debug("Failed to checkout branch %s, using current branch", branch)
                    return existing_dir
            except Exception as exc:  # noqa: BLE001
                # 如果检查失败，继续尝试其他目录或创建新目录
                logger.debug("Failed to check existing repo %s: %s", existing_dir, exc)
                continue
    
    # 没有找到可复用的仓库，创建新的
    repo_path = TEMP_REPOS_DIR / name
    if repo_path.exists():
        logger.info("Using existing repo for %s at %s", name, repo_path)
        return repo_path

    logger.info("Cloning repo %s (%s, branch=%s) into %s", name, url, branch, repo_path)
    Repo.clone_from(url, repo_path, branch=branch)
    return repo_path


def iter_markdown_files(root: Path, subdir: str, limit: int | None) -> List[Path]:
    """
    扫描指定子目录下的 .md 文件，排除：
    - 以 EN.md 结尾的英文文档；
    - 文件名中包含 'summary' 的索引类文档（大小写不敏感）。
    """
    target_root = root / subdir
    if not target_root.exists():
        logger.warning("Subdir not found, skip: %s", target_root)
        return []

    results: List[Path] = []
    for path in target_root.rglob("*.md"):
        # 跳过所有英文目录下的文档（source_en, std_en, libs_stdx_en 等）
        # 检查路径中是否有任何以 _en 结尾的目录名，或包含 source_en 的目录
        if any(part.endswith("_en") or part == "source_en" for part in path.parts):
            continue

        name = path.name
        if name.endswith("EN.md"):
            continue
        if "summary" in name.lower():
            continue
        results.append(path)
        if limit is not None and len(results) >= limit:
            break

    return results


def load_or_create_builder() -> GraphBuilder:
    """
    从本地 JSON 恢复 GraphBuilder 状态，若不存在则返回新的实例。
    """
    if GRAPH_JSON_PATH.exists():
        logger.info("Loading existing graph from %s", GRAPH_JSON_PATH)
        return GraphBuilder.load_json(GRAPH_JSON_PATH)

    logger.info("No existing graph found; creating a new GraphBuilder.")
    return GraphBuilder()


def save_builder(builder: GraphBuilder) -> None:
    builder.save_json(GRAPH_JSON_PATH)


def distill_docs(
    client: OpenAI,
    model: str,
    builder: GraphBuilder,
    limit_per_source: int | None,
) -> None:
    """
    主蒸馏流程：
    - 克隆/复用仓库；
    - 扫描 Markdown 文档；
    - 调用 extractor.extract_graph_from_text 进行文档级蒸馏；
    - 增量合并进 GraphBuilder，并定期保存 JSON。
    """
    processed_files = 0

    for preset_name, cfg in DOC_PRESETS.items():
        repo_path = clone_or_get_repo(preset_name, cfg)
        md_files = iter_markdown_files(repo_path, cfg["subdir"], limit_per_source)
        logger.info(
            "Preset %s: found %d markdown files (limit_per_source=%s)",
            preset_name,
            len(md_files),
            limit_per_source,
        )

        for md_path in md_files:
            try:
                text = md_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to read file %s: %s", md_path, exc, exc_info=True)
                continue

            source_metadata: Dict[str, Any] = {
                "preset": preset_name,
                "file_path": str(md_path),
                "repo_url": cfg["url"],
                "branch": cfg["branch"],
            }

            logger.info("Distilling file: %s", md_path)
            try:
                doc_graph = extract_graph_from_text(
                    client=client,
                    model=model,
                    markdown_text=text,
                    source_metadata=source_metadata,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("extract_graph_from_text failed for %s: %s", md_path, exc, exc_info=True)
                continue

            builder.merge_document_graph(doc_graph)

            processed_files += 1
            if processed_files % 5 == 0:
                logger.info("Processed %d files, saving intermediate graph...", processed_files)
                save_builder(builder)

    # 最后再保存一次
    logger.info("Distillation finished, processed %d files. Saving final graph...", processed_files)
    save_builder(builder)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GraphDistill end-to-end pipeline.")
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("GRAPHDISTILL_MODEL", MODEL),
        help=(
            "LLM 模型名称，默认为环境变量 GRAPHDISTILL_MODEL 或内置模型 "
            f"{MODEL}（SiliconFlow OpenAI-兼容接口）。"
        ),
    )
    parser.add_argument(
        "--debug",
        type=int,
        choices=[0, 1],
        default=0,
        help=(
            "调试开关：0 表示仅从每个数据源的前 5 个文档做抽取；"
            "1 表示对所有可用文档执行全量提取。"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 初始化 SiliconFlow OpenAI-兼容客户端（需环境变量 SILICONFLOW_API_KEY）
    api_key = os.getenv("SILICONFLOW_API_KEY", "")
    if not api_key:
        logger.warning("SILICONFLOW_API_KEY is not set; LLM calls will likely fail.")
    client = OpenAI(base_url=BASE_URL, api_key=api_key)

    # 1) 加载或创建全局 GraphBuilder
    builder = load_or_create_builder()

    # 2) 文档蒸馏流水线
    if args.debug == 0:
        limit_per_source: int | None = 5
        logger.info("Debug 模式开启：每个数据源仅处理前 %d 个文档。", limit_per_source)
    else:
        limit_per_source = None
        logger.info("Debug 模式关闭：对每个数据源执行全量提取。")

    distill_docs(
        client=client,
        model=args.model,
        builder=builder,
        limit_per_source=limit_per_source,
    )

    # 3) 图谱状态报告
    stats = builder.stats_report()
    logger.info("Graph stats: %s", stats)


if __name__ == "__main__":
    main()

