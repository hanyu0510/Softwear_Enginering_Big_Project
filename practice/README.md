# 多人共同编辑与冲突练习

本练习围绕 `team-message.js` 的第 4 行。使用自己的账号和本地克隆，每人提交到同一个远程仓库。

## 两人练习步骤

1. A、B 先运行 `git fetch origin`，记录同一个起点 `git rev-parse origin/develop`。
2. A 从该起点创建分支 `practice/member-a`，B 从该起点创建 `practice/member-b`。
3. A 将第 4 行改成 `return "拾光校园，记录校园活动";`。B 将同一行改成 `return "拾光校园，分享学习日常";`。
4. 两人分别提交并推送各自分支。先把 A 的 PR 合入 `develop`。
5. B 在自己的分支执行 `git fetch origin` 和 `git merge origin/develop`，此时同一行会发生冲突。
6. B 在 VS Code 查看双方修改，与 A 商量后把函数内容改成 `return "拾光校园，记录校园活动，分享学习日常";`，删除冲突标记。
7. B 执行 `git add practice/team-message.js`、`git commit -m "merge: 解决团队欢迎语冲突"`、`git push`，随后完成自己的 PR。
8. 如已安装 Node.js，在仓库根目录执行 `node practice/team-message.js`，检查输出。保留冲突现场、解决后的代码和提交记录截图。

其余成员可两两轮换，每一轮从当前相同的 `origin/develop` 起点开始，协商修改同一行中的其他文字。最后让七人都在此文件上形成自己的提交记录，并将真实链接填写到 `docs/collaboration-record.md`。

对已经完成的共享提交，用后续提交修正。保留原始历史，便于老师核对每位成员的贡献。
