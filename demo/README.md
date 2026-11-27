# 衣搭课堂演示快速启动

本工具支持源码包解压后直接运行。首次安装需要联网和可用的 Python 3.11–3.13、Node.js 20.19+（20.x 系列）或 22.12+、npm。演示本身使用本地回环，不需要外部模型密钥、在线图片或字体。先把压缩包完整解压到可写目录，保留 `frontend/`、`backend/`、`preview/` 和 `demo/` 的相对位置。

## Windows

在资源管理器双击 `demo/setup-demo.bat`。等待看到 `YIDA:` 和本地凭据文件位置。下次双击 `demo/start-demo.bat`，结束时双击 `demo/stop-demo.bat`。脚本使用 Windows 自带的 PowerShell，批处理仅为当前进程放行脚本执行策略。

也可在项目根目录运行以下命令。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\demo\setup-demo.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\demo\start-demo.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\demo\stop-demo.ps1
```

## macOS / Linux

在项目根目录运行以下命令。首次初始化时须能用 `python3 -m venv` 创建虚拟环境，某些 Linux 系统需事先具备对应的 `venv` 软件包。

```sh
sh demo/setup-demo.sh
sh demo/start-demo.sh
sh demo/stop-demo.sh
```

## 登录和演示

打开 [本机课堂入口](http://127.0.0.1:5173/#/login)。账号名为「林予」，邮箱为 `lin.yu.course@example.test`，密码由初始化随机生成。只在自己电脑打开 `backend/data/yida-classroom/state/demo-account.json` 读取 `password`。若浏览器曾连接其他衣搭数据库，建议用新的浏览器配置文件或 InPrivate 窗口打开入口。

1. 浏览首页，打开《一件风衣的三种日常》，切换图片、点赞或收藏。预置内容标明课程样本，互动由公共后端保存。
2. 查看九件衣橱单品。选择 `backend/demo_assets/realistic/gray-lounge-set.png` 手动新增浅灰套装，并查看保存后的详情。模拟识图是可选演示，建议由开发态模拟提供，确认写入实际衣橱。
3. 输入「公园野餐拍照」「美拉德」，开启旅行搭配，搜索罗马并选当天。查看独立规则结果及模拟天气。独立服务使用样本衣橱，公共衣橱中新录入的衣物暂未参与推荐。
4. 在「我的」读取真实资料。发帖可现场编辑与预览，发布和公开关联随公共接口联调。

## 启动故障和重置

| 现象 | 操作 |
| --- | --- |
| Python、Node 或 npm 未找到 | 在新终端用 `python --version`（Windows 可用 `py -3 --version`）、`node --version`、`npm --version` 核对本机工具，随后重试初始化。 |
| 安装时出现网络超时 | 恢复 npm/Python 包源连接后重跑初始化，已有课堂数据会保留。依赖按仓库 `backend/requirements.txt` 和 `frontend/package-lock.json` 初始化。 |
| 5173、8002、8010 被占用 | 检查已有应用，使用原目录中的停止脚本关闭自己的衣搭实例，再启动当前副本。脚本不会终止未知端口的进程。 |
| 入口未启动 | 查看本副本 `backend/data/yida-classroom/state/` 中 `supervisor.log` 与对应服务日志。若初始化被强行中断，确认本目录没有启动任务后才可移除 `backend/data/yida-classroom/launch.lock`。 |
| 推荐请求失败 | 可从失败提示手动进入只读样例，或使用源码包中备用 MP4。 |

首次初始化自动启动三个服务，生成本地媒体、独立 SQLite 和课程账号。普通启动使用已有依赖、媒体和数据库。复跑初始化会检查依赖文件是否变化并保留数据。主动重置需要手动运行 Windows `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\demo\setup-demo.ps1 -Reset`，或 macOS / Linux `sh demo/setup-demo.sh --reset`，按提示输入 `RESET`。它会先把这份副本的课堂 `state` 归档在同一忽略目录，再建立新数据；项目正式库和其他副本各自独立。

课堂模式只在开发态显式启用。公共 FastAPI 在 `127.0.0.1:8002`，规则服务在 `127.0.0.1:8010`，Vue 在 `127.0.0.1:5173`。正式构建在 `frontend/` 中执行 `npm run build`。课程资产由仓库已有样本 `preview/assets/` 和 `backend/demo_assets/realistic/` 生成，保存在本机忽略目录。样本来源与 GitHub 分发授权由团队确认后再对外发布。

Windows PowerShell 5.1 已实际验证。macOS/Linux 脚本已完成 Shell 语法检查，尚未在对应原生系统运行。
