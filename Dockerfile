# Container oficial com Python e dependências do Playwright
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Define diretório de trabalho
WORKDIR /app

# Instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia os arquivos do projeto
COPY src/ ./src/
COPY main.py .

# Variáveis de ambiente padrão
ENV HEADLESS="True"
ENV PYTHONUNBUFFERED="1"

# Comando de execução padrão
CMD ["python", "main.py"]
