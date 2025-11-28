FROM ubuntu:20.04

# 设置非交互式安装
ENV DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /app

# 安装系统依赖和Python
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# 创建Python链接
RUN ln -s /usr/bin/python3 /usr/bin/python

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip3 install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .
COPY monitor.py .
COPY templates/ ./templates/
COPY static/ ./static/

# 创建数据目录
RUN mkdir -p /app/data

# 暴露端口
EXPOSE 5000

# 启动应用
CMD ["python3", "app.py"]

