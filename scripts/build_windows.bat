@echo off
rem SpellForge Windows 打包：产出 dist\SpellForge\SpellForge.exe（onedir + windowed）
rem 前置：Python 3.10+ 与 pip install -r requirements.txt；WebView2 Runtime（Win10/11 一般自带）
rem 状态：未验证 —— 需在真实 Windows 环境构建并按 README 验收清单核对
cd /d "%~dp0.."
python scripts\make_icons.py
python -m PyInstaller --noconfirm --clean desktop\spellforge.spec
echo.
echo 构建完成: dist\SpellForge\SpellForge.exe
echo 冒烟自检: dist\SpellForge\SpellForge.exe --smoke
echo （windowed 模式无控制台输出，结果见 %%APPDATA%%\SpellForge\smoke_result.txt）
