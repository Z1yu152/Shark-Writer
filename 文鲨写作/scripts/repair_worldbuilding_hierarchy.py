# -*- coding: utf-8 -*-
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_ENTRY_PARENTS = {
    "历史纪年": ("世界观", "世界观"),
    "文明规则": ("世界观", "世界观"),
    "黑石码头": ("世界地理", "地点"),
    "旧灯塔": ("世界地理", "地点"),
    "巡逻队": ("组织势力", "组织"),
    "潮汐术": ("能力设定", "能力"),
    "黑盐晶": ("道具物品", "物品"),
}

DEFAULT_MODULE_TITLES = {"世界观", "世界地理", "组织势力", "能力设定", "道具物品"}
DEFAULT_TYPE_BY_PARENT = {
    "世界观": "世界观",
    "世界地理": "地点",
    "组织势力": "组织",
    "能力设定": "能力",
    "道具物品": "物品",
}


def normalize_children(nodes, is_top_level):
    for node in nodes:
        if is_top_level and node.get("kind") == "submenu":
            node["kind"] = "module"
            node.setdefault("default", False)
        elif not is_top_level and node.get("kind") in {"module", "submenu"}:
            node["kind"] = "entry"
            if node.get("entry_type") in {"", "module", "submenu", None}:
                node["entry_type"] = "设定"
            node.pop("default", None)
        node.setdefault("children", [])
        normalize_children(node.get("children", []), False)


def iter_nodes(nodes):
    for node in nodes:
        yield node
        yield from iter_nodes(node.get("children", []))


def infer_legacy_parent(node):
    direct_parent, direct_type = DEFAULT_ENTRY_PARENTS.get(node.get("title"), (None, None))
    if direct_parent:
        return direct_parent, direct_type
    if node.get("default") or node.get("title") in DEFAULT_MODULE_TITLES:
        return None, None
    if node.get("entry_type") != "submenu":
        return None, None

    parent_votes = {}
    type_votes = {}
    for child in iter_nodes(node.get("children", [])):
        child_parent, child_type = DEFAULT_ENTRY_PARENTS.get(child.get("title"), (None, None))
        if child_parent:
            parent_votes[child_parent] = parent_votes.get(child_parent, 0) + 1
        if child_type:
            type_votes[child_type] = type_votes.get(child_type, 0) + 1
    if not parent_votes:
        return None, None
    parent_title = max(parent_votes, key=parent_votes.get)
    entry_type = max(type_votes, key=type_votes.get) if type_votes else DEFAULT_TYPE_BY_PARENT.get(parent_title, "设定")
    return parent_title, entry_type


def repair(world):
    modules = world.get("modules", [])
    normalize_children(modules, True)
    modules_by_title = {module.get("title"): module for module in modules if module.get("kind") == "module"}
    normalized = []
    moved_ids = set()

    for module in modules:
        parent_title, entry_type = infer_legacy_parent(module)
        target_parent = modules_by_title.get(parent_title) if parent_title else None
        if target_parent and target_parent is not module:
            module["kind"] = "entry"
            module["entry_type"] = entry_type or DEFAULT_TYPE_BY_PARENT.get(parent_title, "设定")
            module.pop("default", None)
            target_parent.setdefault("children", [])
            if not any(child.get("id") == module.get("id") for child in target_parent["children"]):
                target_parent["children"].append(module)
            moved_ids.add(module.get("id", ""))
        else:
            normalized.append(module)

    world["modules"] = [module for module in normalized if module.get("id") not in moved_ids]
    return len(moved_ids)


def main():
    if len(sys.argv) != 2:
        print("usage: repair_worldbuilding_hierarchy.py <draft.json>")
        return 2

    draft_path = Path(sys.argv[1])
    data = json.loads(draft_path.read_text(encoding="utf-8"))
    world = data.setdefault("worldbuilding", {})
    moved = repair(world)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = draft_path.with_name(f"{draft_path.stem}.before_worldbuilding_repair_{stamp}{draft_path.suffix}")
    shutil.copy2(draft_path, backup_path)
    draft_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"moved={moved}")
    print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
