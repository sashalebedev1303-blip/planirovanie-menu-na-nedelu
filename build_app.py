import PyInstaller.__main__
import os
import shutil

# Имя вашего главного файла
MAIN_SCRIPT = 'main.py'
# Имя папки, которая будет создана
APP_NAME = 'DachaApp'

# Очистка старых сборок (если есть)
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('dist'):
    shutil.rmtree('dist')

print("Начинаю сборку...")

PyInstaller.__main__.run([
    MAIN_SCRIPT,
    '--name=%s' % APP_NAME,
    '--onedir',              
    '--noconsole',           
    '--add-data=dacha.db;.',    
    '--add-data=dishes.csv;.',
    '--hidden-import=uvicorn.logging',
    '--hidden-import=uvicorn.loops',
    '--hidden-import=uvicorn.loops.auto',
    '--hidden-import=uvicorn.protocols',
    '--hidden-import=uvicorn.protocols.http',
    '--hidden-import=uvicorn.protocols.http.auto',
    '--hidden-import=uvicorn.protocols.websockets',
    '--hidden-import=uvicorn.protocols.websockets.auto',
    '--hidden-import=uvicorn.lifespan',
    '--hidden-import=uvicorn.lifespan.on',
])

print("Сборка завершена! Проверьте папку 'dist'.")
