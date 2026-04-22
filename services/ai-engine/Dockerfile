FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用
COPY . .

# 创建缓存目录
RUN mkdir -p /app/cache

EXPOSE 8001

CMD ["python", "main.py"]
