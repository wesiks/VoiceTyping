import os
import sys
import ast
import time
import shutil
import subprocess
from pathlib import Path

def get_external_dependencies(src_dir: Path):
    deps = set()
    src_mod_names = {p.stem for p in src_dir.glob("*.py")}
    for py_file in src_dir.glob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top not in src_mod_names:
                            deps.add(alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    top = node.module.split(".")[0]
                    if top not in src_mod_names:
                        deps.add(node.module)
        except Exception:
            pass

    deps.update([
        "logging.handlers",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtNetwork",
        "sounddevice",
        "numpy",
        "requests",
        "vosk",
        "queue",
        "wave",
        "json"
    ])
    return sorted(list(deps))

def compile_modules_to_pyd(base_dir: Path, staging_dir: Path):
    src_dir = base_dir / "src"
    staging_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = base_dir / "build" / "cython_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    py_files = sorted([p for p in src_dir.glob("*.py") if p.name != "__init__.py"])
    print(f"[*] Компиляция {len(py_files)} модулей в нативные C-расширения (.pyd)...")

    python_exe = str(base_dir / ".venv" / "Scripts" / "python.exe")
    if not Path(python_exe).exists():
        python_exe = sys.executable

    compile_script = base_dir / "build" / "_compile_worker.py"
    worker_code = f"""import sys
import shutil
from pathlib import Path
from setuptools import setup
from Cython.Build import cythonize

src_dir = Path(r"{src_dir}")
staging_dir = Path(r"{staging_dir}")
temp_dir = Path(r"{temp_dir}")

py_files = sorted([str(p) for p in src_dir.glob("*.py") if p.name != "__init__.py"])

sys.argv = ["setup.py", "build_ext", f"--build-lib={{staging_dir}}", f"--build-temp={{temp_dir}}"]

setup(
    ext_modules=cythonize(
        py_files,
        language_level=3,
        compiler_directives={{"language_level": "3", "always_allow_keywords": True}}
    )
)

for pyd in staging_dir.rglob("*.pyd"):
    if pyd.parent != staging_dir:
        dest = staging_dir / pyd.name
        shutil.copy2(pyd, dest)

sub_src = staging_dir / "src"
if sub_src.exists():
    try:
        shutil.rmtree(sub_src)
    except Exception:
        pass

for pyd in staging_dir.glob("*.pyd"):
    parts = pyd.name.split(".")
    if len(parts) >= 3 and parts[-1] == "pyd":
        clean_name = f"{{parts[0]}}.pyd"
        clean_dest = staging_dir / clean_name
        if not clean_dest.exists():
            shutil.copy2(pyd, clean_dest)

(staging_dir / "__init__.py").write_text("", encoding="utf-8")
"""
    compile_script.write_text(worker_code, encoding="utf-8")

    try:
        subprocess.run([python_exe, str(compile_script)], cwd=base_dir, check=True)
    finally:
        if compile_script.exists():
            try:
                compile_script.unlink()
            except Exception:
                pass
        for c_file in src_dir.glob("*.c"):
            try:
                c_file.unlink()
            except Exception:
                pass

    pyd_count = len(list(staging_dir.glob("*.pyd")))
    print(f"[*] Успешно создано {pyd_count} нативных C-бинарников (.pyd) в {staging_dir.name}")
    return staging_dir

def main():
    print("=" * 60)
    print("  Сборка VoiceTyping (Нативная бинарная защита кода)")
    print("=" * 60)

    base_dir = Path(__file__).resolve().parent

    subprocess.run(["taskkill", "/F", "/IM", "VoiceTyping.exe"], capture_output=True)
    try:
        subprocess.run([
            "powershell", "-NoProfile", "-Command",
            "$app = New-Object -ComObject Shell.Application; "
            "$app.Windows() | Where-Object { $_.LocationURL -like '*VoiceTyping*' } | ForEach-Object { $_.Quit() }"
        ], capture_output=True)
    except Exception:
        pass

    build_dir = base_dir / "build"
    dist_app_dir = base_dir / "dist" / "VoiceTyping"

    if build_dir.exists():
        try:
            shutil.rmtree(build_dir)
        except Exception:
            pass

    if dist_app_dir.exists():
        try:
            shutil.rmtree(dist_app_dir)
        except Exception:
            pass

    hidden_deps = get_external_dependencies(base_dir / "src")
    print(f"[*] Автоматически обнаружено внешних зависимостей: {len(hidden_deps)}")

    staging_src = base_dir / "build" / "staging_src"
    compile_modules_to_pyd(base_dir, staging_src)

    venv_vosk = base_dir / ".venv" / "Lib" / "site-packages" / "vosk"
    if not venv_vosk.exists():
        try:
            import vosk
            venv_vosk = Path(vosk.__file__).resolve().parent
        except Exception:
            pass

    icon_path = base_dir / "app.ico"

    models_dir = base_dir / "models" / "vosk-model-small-ru-0.22"
    if not models_dir.exists():
        user_cache = Path.home() / ".cache" / "vosk" / "vosk-model-small-ru-0.22"
        if user_cache.exists():
            try:
                models_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(user_cache, models_dir)
                print("[*] Автоматически скопирована модель Vosk из кэша пользователя в models/")
            except Exception as e:
                print(f"[!] Не удалось скопировать модель: {e}")

    pyinstaller_exe = str(base_dir / ".venv" / "Scripts" / "pyinstaller.exe")
    if not Path(pyinstaller_exe).exists():
        pyinstaller_exe = shutil.which("pyinstaller") or "pyinstaller"

    cmd = [
        pyinstaller_exe,
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--optimize", "2",
        "--name", "VoiceTyping",
        "--icon", str(icon_path),
        "--collect-all", "vosk",
        "--add-data", f"{venv_vosk};vosk",
        "--add-data", "app.ico;.",
        "--add-data", "version.json;.",
        "--add-data", "PRIVACY.md;.",
        "--add-data", "TERMS.md;.",
        "--add-data", f"{staging_src};src",
        "--add-data", "fonts;fonts",
        "--add-data", "models;models",
        "--paths", str(staging_src),
        "--paths", "src",
    ]

    for dep in hidden_deps:
        cmd.extend(["--hidden-import", dep])

    cmd.append("main.py")

    sys32 = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
    msvc_dlls = [
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    ]
    found_msvc = []
    for dll_name in msvc_dlls:
        p = sys32 / dll_name
        if p.exists():
            found_msvc.append(p)
            cmd.extend(["--add-binary", f"{p};."])

    print(f"[*] Найдено MSVC DLLs для упаковки: {len(found_msvc)}")

    print("[*] Запуск PyInstaller с оптимизацией байткода...")
    ret = subprocess.run(cmd, cwd=base_dir)

    if ret.returncode == 0:
        internal_dir = dist_app_dir / "_internal"
        for dll_path in found_msvc:
            try:
                shutil.copy2(dll_path, dist_app_dir / dll_path.name)
            except Exception:
                pass
            if internal_dir.exists():
                try:
                    shutil.copy2(dll_path, internal_dir / dll_path.name)
                except Exception:
                    pass

        dist_root_src = dist_app_dir / "src"
        if not dist_root_src.exists() and staging_src.exists():
            try:
                shutil.copytree(staging_src, dist_root_src)
            except Exception:
                pass

        for target_src in [dist_root_src, internal_dir / "src"]:
            if target_src.exists():
                sub_s = target_src / "src"
                if sub_s.exists():
                    try:
                        shutil.rmtree(sub_s)
                    except Exception:
                        pass
                for py_file in target_src.glob("*.py"):
                    if py_file.name != "__init__.py":
                        try:
                            py_file.unlink()
                        except Exception:
                            pass

        models_src = base_dir / "models"
        if models_src.exists():
            models_dist = dist_app_dir / "models"
            if not models_dist.exists():
                try:
                    shutil.copytree(models_src, models_dist)
                    print("[*] Скопированы оффлайн модели Vosk в dist\\VoiceTyping\\models")
                except Exception as e:
                    print(f"[!] Ошибка копирования моделей в root: {e}")

        debug_bat = dist_app_dir / "VoiceTyping_Debug.bat"
        debug_bat_content = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "title VoiceTyping - Режим диагностики\r\n"
            "echo ======================================================\r\n"
            "echo      VoiceTyping - Запуск в режиме диагностики/логов\r\n"
            "echo ======================================================\r\n"
            "echo.\r\n"
            "echo Журнал работы (логи) сохраняется в папку:\r\n"
            "echo   %%APPDATA%%\\VoiceTyping\\logs\\voicetyping.log\r\n"
            "echo.\r\n"
            "cd /d \"%~dp0\"\r\n"
            "VoiceTyping.exe\r\n"
            "echo.\r\n"
            "echo [!] VoiceTyping завершил работу с кодом: %errorlevel%\r\n"
            "echo Если приложение закрылось с ошибкой, откройте voicetyping.log\r\n"
            "echo.\r\n"
            "pause\r\n"
        )
        try:
            debug_bat.write_text(debug_bat_content, encoding="utf-8")
            print("[*] Создан скрипт диагностики: VoiceTyping_Debug.bat")
        except Exception as e:
            print(f"[!] Не удалось создать VoiceTyping_Debug.bat: {e}")

        if build_dir.exists():
            try:
                shutil.rmtree(build_dir)
            except Exception:
                pass

        pyd_in_dist = list((dist_app_dir / "_internal" / "src").glob("*.pyd")) if (dist_app_dir / "_internal" / "src").exists() else []
        py_in_dist = [p for p in (dist_app_dir / "_internal" / "src").glob("*.py") if p.name != "__init__.py"] if (dist_app_dir / "_internal" / "src").exists() else []

        print()
        print("=" * 60)
        print("[УСПЕХ] Сборка успешно завершена с защитой кода!")
        print(f"[*] Скомпилировано нативных C-модулей (.pyd): {len(pyd_in_dist)}")
        print(f"[*] Открытых исходных файлов (.py): {len(py_in_dist)} (полностью скрыты)")
        print("Готовая программа: dist\\VoiceTyping\\VoiceTyping.exe")
        print("=" * 60)
    else:
        print("[!] Ошибка во время сборки.")
        sys.exit(1)

if __name__ == "__main__":
    main()
