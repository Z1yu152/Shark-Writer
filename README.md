# 文鲨创作

文鲨创作是一款 Python 本地桌面小说创作辅助软件，面向长篇小说写作场景，核心能力包括正文写作、项目管理、大纲、设定库、人物卡、关系记录、时间线和 AI 辅助。

## 当前状态

- 运行形态：Python 本地桌面程序
- UI 框架：PySide6 / Qt for Python
- 数据方向：SQLite + 本地项目文件夹
- 启动入口：`文鲨写作/run_app.py`
- 主要源码：`文鲨写作/novel_assistant/main.py`

当前仓库作为源码备份使用，不包含本机运行状态、个人 API Key、临时项目、构建缓存和打包输出。

## 本地运行

```powershell
cd 文鲨写作
python -m pip install -r ..\requirements.txt
python run_app.py
```

如果使用指定 Python 环境，请先激活环境后再运行以上命令。

## 目录说明

```text
文鲨写作/
  run_app.py                 程序启动入口
  novel_assistant/           主程序源码
  assets/brand/              品牌图标和 logo
  scripts/                   测试、诊断和开发辅助脚本
```

## 未纳入备份的内容

- `文鲨写作/.app_state/`：本机设置、最近项目、可能包含 API Key
- `文鲨写作/build/`、`文鲨写作/dist/`：构建产物
- `__pycache__/`、`*.egg-info/`：Python 缓存与构建元数据
- `文鲨写作/tmp*/`、`文鲨写作/wensha_v*/`：临时或样例项目
- `文鲨写作/qa_*.png`、`ui_concepts*/`：界面截图和概念图
- `小说辅助软件需求文档_v*.docx`：旧版需求迭代稿

## 打包说明

当前目录中的历史打包产物不作为已验证的独立安装包。此前 PyInstaller / cx_Freeze 构建曾出现 PySide6 QtCore/QtWidgets DLL 加载问题；后续发布前需要先验证最小 Qt 程序，再验证完整应用的独立 exe。
