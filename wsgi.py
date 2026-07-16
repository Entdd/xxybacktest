"""PythonAnywhere WSGI 入口"""
import os
import sys

# 项目路径
project_path = os.path.expanduser("~/xxybacktest")
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# 设置数据路径
os.environ["XXY_DATA_PATH"] = os.path.join(project_path, "data")

from xxybacktest.web.app import create_app
application = create_app()
