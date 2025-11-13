import threading
import time
import tkinter as tk
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS
import MetaTrader5 as mt5
import logging
from waitress import serve
import pystray
from PIL import Image, ImageDraw

# ===========================================
# 🧾 LOGGING
# ===========================================
logging.basicConfig(
    filename="server.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logging.info("🚀 Iniciando servidor...")

# ===========================================
# 🌐 FLASK APP
# ===========================================
app = Flask(__name__)
CORS(app)

# ===========================================
# ⚙️ CONFIGURACIONES GLOBALES
# ===========================================
config = {
    "dias_filtrado": 365,
    "ip_blanca": []
}

# ===========================================
# 🔐 FILTRO DE IP
# ===========================================
@app.before_request
def verificar_ip():
    ip_cliente = request.remote_addr
    if config["ip_blanca"]:
        if ip_cliente not in config["ip_blanca"]:
            logging.warning(f"❌ IP no autorizada: {ip_cliente}")
            return jsonify({"error": "IP no autorizada"}), 403

# ===========================================
# 🔌 MT5 Conexión
# ===========================================
@app.before_request
def conectar_mt5():
    if not mt5.initialize():
        err = mt5.last_error()
        logging.error(f"Error al conectar MT5: {err}")
        return jsonify({"error": "No se pudo conectar a MetaTrader 5", "codigo": err}), 500

@app.teardown_request
def cerrar_mt5(exception):
    mt5.shutdown()

# ===========================================
# 📊 Funciones MT5
# ===========================================
def obtener_estadistica_dia():
    try:
        now = datetime.now()
        start = now - timedelta(days=config["dias_filtrado"])
        end = now + timedelta(days=1)
        deals_today = mt5.history_deals_get(start, end)

        if deals_today is None:
            err = mt5.last_error()
            logging.error(f"No se pudieron obtener operaciones: {err}")
            return {"error": f"No se pudieron obtener operaciones: {err}"}

        closed_today = [d for d in deals_today if not (d.type == 2 and d.symbol == "")]
        info = mt5.account_info()
        balance = info.balance if info else 0
        equity = info.equity if info else 0
        margin = info.margin if info else 0

        total_profit = sum(d.profit for d in closed_today)
        ganadoras = [d for d in closed_today if d.profit > 0]
        perdedoras = [d for d in closed_today if d.profit < 0]
        total_ops = len(closed_today)

        ratio = round(len(ganadoras) / total_ops * 100, 2) if total_ops else 0
        promedio = round(total_profit / total_ops, 2) if total_ops else 0

        return {
            "total_operaciones": total_ops,
            "ganadoras": len(ganadoras),
            "perdedoras": len(perdedoras),
            "ratio_ganadoras": f"{ratio}%",
            "beneficio_total": round(total_profit, 2),
            "promedio_por_operacion": promedio,
            "balance": balance,
            "equity": equity,
            "margin": margin,
            "dias_filtrados": config["dias_filtrado"]
        }

    except Exception as e:
        logging.error(f"Error inesperado en obtener_estadistica_dia: {e}")
        return {"error": f"Error inesperado: {e}"}

def operaciones_abiertas():
    positions = mt5.positions_get()
    return [p._asdict() for p in positions] if positions else []

# ===========================================
# 🔹 MONITOR
# ===========================================
solicitudes_totales = 0
solicitudes_por_minuto = 0
log_solicitudes = []
lock = threading.Lock()

def reset_contador():
    global solicitudes_por_minuto
    while True:
        time.sleep(60)
        with lock:
            solicitudes_por_minuto = 0

threading.Thread(target=reset_contador, daemon=True).start()

@app.before_request
def registrar_solicitud():
    global solicitudes_totales, solicitudes_por_minuto, log_solicitudes
    if request.headers.get("X-Internal-Ping") != "true":
        with lock:
            solicitudes_totales += 1
            solicitudes_por_minuto += 1
            log_solicitudes.append({
                "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "endpoint": request.path,
                "metodo": request.method,
                "ip": request.remote_addr,
            })
            if len(log_solicitudes) > 500:
                log_solicitudes.pop(0)

# ===========================================
# 🌐 ENDPOINTS
# ===========================================
@app.route("/api/balance")
def api_balance():
    logging.info("📡 /api/balance")
    return jsonify(obtener_estadistica_dia())

@app.route("/api/opentrader")
def api_opentrader():
    logging.info("📡 /api/opentrader")
    return jsonify(operaciones_abiertas())

@app.route("/api/daytrade", methods=["GET"])
def api_daytrade():
    logging.info("📡 /api/daytrade")
    now = datetime.now()
    start = now - timedelta(days=config["dias_filtrado"])
    end = now + timedelta(days=1)
    deals = mt5.history_deals_get(start, end)
    if deals is None:
        err = mt5.last_error()
        logging.error(f"No se pudieron obtener las órdenes: {err}")
        return jsonify({"error": "No se pudieron obtener las órdenes", "codigo": err})
    daytrade = [d._asdict() for d in deals if d.type != 2]
    return jsonify(daytrade)

@app.route("/monitor")
def monitor():
    with lock:
        return jsonify({
            "estado": "Conectado",
            "solicitudes_por_minuto": solicitudes_por_minuto,
            "solicitudes_totales": solicitudes_totales,
            "log_solicitudes": log_solicitudes[-10:],
            "dias_filtrado": config["dias_filtrado"],
            "ip_blanca": config["ip_blanca"]
        })

# ===========================================
# 🟢 INTERFAZ TKINTER
# ===========================================
def iniciar_interfaz():
    root = tk.Tk()
    root.title("Monitor MT5")

    lbl_estado = tk.Label(root, text="Estado: ---")
    lbl_estado.pack()

    lbl_solicitudes = tk.Label(root, text="Solicitudes/minuto: ---")
    lbl_solicitudes.pack()

    lbl_totales = tk.Label(root, text="Solicitudes totales: ---")
    lbl_totales.pack()

    # Campo para cambiar días
    frame_dias = tk.Frame(root)
    frame_dias.pack(pady=5)
    tk.Label(frame_dias, text="Días de filtrado:").pack(side="left")
    entry_dias = tk.Entry(frame_dias, width=6)
    entry_dias.insert(0, str(config["dias_filtrado"]))
    entry_dias.pack(side="left")

    def aplicar_dias():
        try:
            config["dias_filtrado"] = int(entry_dias.get())
            logging.info(f"🔄 Días de filtrado actualizados a {config['dias_filtrado']}")
        except ValueError:
            logging.warning("⚠️ Valor inválido para días")

    tk.Button(frame_dias, text="Aplicar", command=aplicar_dias).pack(side="left", padx=5)

    # Campo IP blanca
    frame_ip = tk.Frame(root)
    frame_ip.pack(pady=5)
    tk.Label(frame_ip, text="IP Blanca(s):").pack(side="left")
    entry_ip = tk.Entry(frame_ip, width=25)
    entry_ip.pack(side="left")

    def aplicar_ip():
        ips = [ip.strip() for ip in entry_ip.get().split(",") if ip.strip()]
        config["ip_blanca"] = ips
        logging.info(f"🔒 IPs autorizadas: {ips}")

    tk.Button(frame_ip, text="Aplicar", command=aplicar_ip).pack(side="left", padx=5)

    # Log de solicitudes
    tk.Label(root, text="Últimas solicitudes:").pack()
    txt_log = tk.Text(root, height=10, width=80)
    txt_log.pack()

    def actualizar():
        try:
            resp = requests.get("http://127.0.0.1/monitor", headers={"X-Internal-Ping": "true"}, timeout=2)
            data = resp.json()
            lbl_estado.config(text=f"Estado: {data['estado']}", foreground="green")
            lbl_solicitudes.config(text=f"Solicitudes/minuto: {data['solicitudes_por_minuto']}")
            lbl_totales.config(text=f"Solicitudes totales: {data['solicitudes_totales']}")
            txt_log.delete(1.0, tk.END)
            for entrada in data["log_solicitudes"]:
                txt_log.insert(tk.END, f"{entrada['hora']} | {entrada['ip']} | {entrada['metodo']} | {entrada['endpoint']}\n")
        except:
            lbl_estado.config(text="Estado: 🔴 Desconectado", foreground="red")

        root.after(2000, actualizar)

    actualizar()
    root.mainloop()

# ===========================================
# ▶️ EJECUCIÓN
# ===========================================
def iniciar_servidor():
    serve(app, host="0.0.0.0", port=80)

if __name__ == "__main__":
    threading.Thread(target=iniciar_servidor, daemon=True).start()
    time.sleep(1)
    iniciar_interfaz()
