FROM python:3.12-slim

WORKDIR /app

# 系统依赖 + pip
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple pip --upgrade

# Python 依赖 (分层缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 源码
COPY . .

# 本地包安装
RUN pip install -e . --no-deps

EXPOSE 5000

CMD ["python", "run_simulation.py"]
