---
name: ok-kes-build-shortcut
description: After a successful ok-kes PyInstaller build, create or replace a Windows desktop shortcut to the exe that was just built. Use whenever build_exe.bat, PyInstaller, or a request to compile, build, or package ok-kes finishes successfully.
---

# ok-kes 编译后创建桌面快捷方式

`build_exe.bat` 或等价的 PyInstaller 打包成功之后，立刻在当前用户桌面创建快捷方式。不要再问用户要不要建。

## 规则

- 只在编译成功、`dist` 里的 exe 已经写完之后执行。编译失败就不要建。
- 快捷方式指向刚才这次编译产出的 exe，不要指到旧文件。
  - `build_exe.bat` → `dist/ok-kes-win32-portable.exe`
  - `build_exe.bat <后缀>` → `dist/ok-kes-win32-portable-<后缀>.exe`，例如 `dev` 得到 `dist/ok-kes-win32-portable-dev.exe`
- 桌面上固定使用同一个名字 `ok-kes.lnk`，每次覆盖，指向最新一次编出来的 exe。
- 起始位置设为 exe 所在的 `dist` 目录。图标用 exe 自带图标。

## 做法

在仓库根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/ok-kes-build-shortcut/scripts/create_desktop_shortcut.ps1 -ExePath "dist\ok-kes-win32-portable-dev.exe"
```

把 `-ExePath` 换成这次实际产出的 exe。脚本会打印快捷方式的完整路径。回复用户时带上这个路径，以及它指向的 exe。
