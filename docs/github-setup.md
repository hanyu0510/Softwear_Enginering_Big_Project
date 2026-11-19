# GitHub 远程仓库设置

## 远程初始化

在 GitHub 的 New repository 页面使用名称 `shiguang-campus`，建议选择 Private。此项目已有本地初始化提交，因此远程创建时保持为空，不额外勾选 README、gitignore 或 License。

创建完成后，在本地仓库目录执行以下命令，将地址中的所有者替换为创建页面显示的账号。

```powershell
git remote add origin https://github.com/仓库所有者/shiguang-campus.git
git push -u origin main
git push -u origin develop
```

如 `origin` 已存在，先运行 `git remote -v` 核对地址，只推送到本组确认的仓库。可以使用 `git remote set-url origin 正确地址` 更正。

## 邀请组员

在仓库 Settings 的 Collaborators 页面，使用六位成员的 GitHub 用户名添加协作者。成员接受邀请后克隆同一个仓库，各自在自己的功能分支提交。私有仓库访问需要账号权限。

## 建立基础任务

根据 `docs/team.md` 为每个开发模块建立 Issue，写清负责人、接口对接人和验收条件。组员可在 Issues 使用已经配置好的功能需求和问题反馈模板。

## 发布与分支

默认分支使用 `main`，日常 PR 目标使用 `develop`。完成阶段验收后，将 `develop` 通过 PR 合入 `main`。基础版验收时可创建 `v0.1.0` 标签，期末交付时再创建正式版本标签，便于对应报告和展示材料。
