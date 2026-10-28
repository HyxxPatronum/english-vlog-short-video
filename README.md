# 英语 VLOG 短视频制作流程

可复用的 Codex skill：从英语 VLOG 原片制作双语字幕、知识点回听与讲解、无字幕盲听、抖音时间轴，以及确认后的知识点总卡。

## 下载与使用

下载仓库 ZIP，将其解压或克隆为 `english-vlog-short-video`，放入 Codex 的 `skills` 目录。调用 `english-vlog-short-video`，提供原视频和本集期数；按 skill 流程确认知识点、卡片文稿及配音素材。

## 文件

- `SKILL.md`：制作流程、交互节点和版式标准
- `config/series-params.json`：系列固定参数及资产校验值
- `config/episode-manifest.example.json`：单集验收输入模板
- `references/production-and-qa.md`：逐集记录与人工验收清单
- `scripts/`：系列参数、字幕、卡片和成片的自动校验及卡片渲染脚本
- `assets/`：兔子动画、固定水印、分帧图和转场音效

原视频、人物画面、单集配音、脚本及导出成片不属于 skill 包。公开下载不自动授予系列美术或音效素材的二次分发或商业使用许可；使用前请确认对应授权。
