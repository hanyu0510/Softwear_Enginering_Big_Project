# 七人协作指南

## 首次加入

1. 接受组长发送的 GitHub 仓库邀请。
2. 在 GitHub 仓库页面复制 HTTPS 地址。
3. 在你自己的电脑执行以下命令，将占位地址替换为真实地址。

```powershell
git clone https://github.com/仓库所有者/shiguang-campus.git
cd shiguang-campus
git switch develop
git config user.name "你的姓名或GitHub用户名"
git config user.email "你在GitHub验证过的邮箱或GitHub提供的noreply邮箱"
```

GitHub 首次推送可能要求浏览器登录。Git 提交邮箱用于标识提交作者，填写前核对拼写。

## 每次开发

以下以动态发布模块为例，每个成员替换为自己的分支名和文件路径。

```powershell
git switch develop
git pull --ff-only origin develop
git switch -c feature/member2-post-publish
# 使用编辑器编写代码，完成本模块的运行验证。
git status
git add miniprogram/
git diff --cached
git commit -m "feat: 实现动态发布页面"
git push -u origin feature/member2-post-publish
```

在 GitHub 创建 Pull Request，将目标分支设为 `develop`，填写功能、验证结果和关联任务。对接的前端或后端同学确认接口能运行后合并。全组验收后，再通过 PR 将 `develop` 合入 `main`。

一个 PR 尽量围绕一项功能。成员可以主动请求一位对接人检查，仓库初始化阶段不强制设置审批人数。

## 分支建议

| 成员 | 分支示例 |
| --- | --- |
| 汉雨 | `feature/account-pages`、`feature/statistics` |
| 成员 2 | `feature/post-publish` |
| 成员 3 | `feature/feed-interactions` |
| 成员 4 | `feature/auth-interaction-api` |
| 成员 5 | `feature/content-media-api` |
| 成员 6 | `feature/admin-management` |
| 成员 7 | `test/core-scenarios`、`docs/test-report` |

## 合并前同步

在自己的功能分支上执行，先保存或提交工作区改动。

```powershell
git fetch origin
git merge origin/develop
# 如提示冲突，在 VS Code 中打开标记为冲突的文件。
# 保留双方需要的内容，删除冲突标记，再运行代码确认结果。
git add 发生冲突的文件路径
git commit -m "merge: 解决功能分支与develop的冲突"
git push
```

`git status` 可以确认是否还有未解决的文件。需要放弃尚未完成的本次合并时，可执行 `git merge --abort`。已经合并到公共分支的错误，通过修复提交或 `git revert` 撤销，并告知相关成员。

## 文件与材料

各模块共用同一份接口约定 `docs/api-contract.md`。调整字段时，先同步对应模块负责人并更新文档。Word 和 PPT 按文件安排负责人，同一时间由一位成员编辑并提交，其他人提供修改意见。课程冲突练习使用可逐行合并的代码文件。

本地数据库密码、API Key、小程序私人配置和用户上传原始视频保留在各自运行环境。可复现的配置示例使用 `.env.example` 或示例配置文件，填入占位值。数据库迁移按顺序新增 SQL 文件。

## 任务管理

基础任务使用功能需求模板创建 Issue，明确负责人和验收条件。缺陷使用问题反馈模板，填写复现步骤、实际结果和预期结果。项目开发阶段每周至少进行一次跨模块联调，并把验证结果写入 PR 或 Issue。
