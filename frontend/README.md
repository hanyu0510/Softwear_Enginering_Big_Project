# 衣搭前端运行与开发

Vue 3、Vite、Vue Router 和 TDesign Mobile Vue。项目使用 Hash 路由与系统字体。第一阶段的功能已冻结，第二阶段联调边界见 [功能状态](docs/feature-status.md)。

## 本地开发

使用 Node.js 20.19+（20.x）或 22.12+ 与 npm 9+。从仓库根目录执行：

```sh
cd frontend
npm ci
npm run dev
```

Vite 默认监听 `127.0.0.1:5173`，开发和本地生产预览均将 `/api/v1` 代理到 `127.0.0.1:8002`。仅启动前端可打开页面壳，完整业务需要公共 FastAPI。通过 [课堂演示工具](../demo/README.md) 可同时初始化和启动前端、公共后端与独立规则推荐。

课堂课程模式由共享启动工具显式启用。它用独立规则和带标记的样本数据，公共认证和衣橱仍使用同源公共 API。Windows PowerShell 5.1 已实测，macOS/Linux Shell 脚本目前完成语法检查。

## 构建与验收

```sh
npm run build
npm run preview -- --port 4173 --strictPort
```

产物在 `dist/`。正式构建关闭课堂推荐、模拟识图入口与课程媒体代理。生产部署需在站点同源提供 `/api/v1`，并完成后端安全和跨模块联调。完成授权核对后再对外发布摄影与样例素材。

- [视觉设计规范](docs/design-system.md)
- [前端开发对齐文档增补](docs/frontend-contract-supplement.md)
- [已实现功能与待联调项](docs/feature-status.md)
