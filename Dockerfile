# 使用固定的稳定的 Debian bookworm 版本，防止底层系统更新导致报错
FROM python:3.11-slim-bookworm

# 1. 以 root 身份安装系统依赖 (使用 libgl1 替代 libgl1-mesa-glx)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 sudo && \
    rm -rf /var/lib/apt/lists/*

# 2. 创建 Hugging Face 要求的非 root 用户 (UID 1000)
RUN useradd -m -u 1000 user

# 3. 切换到该用户
USER user

# 4. 设置环境变量
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONPATH=/home/user/app \
    PYTHONUNBUFFERED=1

# 5. 设置工作目录
WORKDIR $HOME/app

# 6. 复制 requirements.txt 并设置所有权
COPY --chown=user requirements.txt .

# 7. 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 8. 复制所有代码并设置所有权
COPY --chown=user . .

# 9. 创建输出目录并确保权限正确
RUN mkdir -p $HOME/app/tmp_outputs

# 10. 暴露端口
EXPOSE 7860

# 11. 启动命令
CMD ["python", "app.py"]
