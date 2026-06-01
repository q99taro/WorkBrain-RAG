# 使用輕量級的 Python 3.10 映像檔
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製環境清單並安裝套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 將專案內的所有檔案複製到容器中
COPY . .

# 開放 Hugging Face Spaces 預設的 7860 通訊埠
EXPOSE 7860

# 啟動 FastAPI 伺服器
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]