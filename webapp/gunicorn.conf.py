bind = "0.0.0.0:5000"
# Un único proceso con hilos: las métricas de prometheus_client viven en memoria
# y con varios workers cada uno expondría solo sus propios contadores.
workers = 1
threads = 8
worker_class = "gthread"
timeout = 120
accesslog = "-"
errorlog = "-"
forwarded_allow_ips = "*"
