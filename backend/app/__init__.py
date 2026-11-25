# -*- coding: utf-8 -*-
"""应用包。目录结构按开发对齐文档 4.3 的建议：

backend/app/
  core/                      # 公共能力：数据库、响应、错误、鉴权依赖
  modules/community/         # 社区模块（首页信息流属于这里）
  main.py                    # 公共入口（正式工程用，注册所有模块路由）
"""
