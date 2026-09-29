# Publish as a separate GitHub template repository

Recommended repository name: `blender-architecture-template`

## GitHub CLI

```bash
git init
git add .
git commit -m "Initial Blender architecture teaching template"
git branch -M main
gh repo create blender-architecture-template --public --source=. --remote=origin --push
```

จากนั้นเปิด GitHub **Settings → General** แล้ว enable **Template repository** เพื่อให้ผู้เรียนเห็นปุ่ม **Use this template**.

สำหรับเว็บ 3D ให้เปิด **Settings → Pages → Source: GitHub Actions**.
