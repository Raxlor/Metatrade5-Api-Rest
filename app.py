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
# 🔌 MT5 Conexión
# ===========================================
@app.before_request
def conectar_mt5():
    if not mt5.initialize():
        err = mt5.last_error()
        logging.error(f"Error al conectar MT5: {err}")
        return (
            jsonify({"error": "No se pudo conectar a MetaTrader 5", "codigo": err}),
            500,
        )


@app.teardown_request
def cerrar_mt5(exception):
    mt5.shutdown()

# ===========================================
# 📊 Funciones MT5
# ===========================================
def obtener_estadistica_dia():
    try:
        now = datetime.now()
        start = now - timedelta(days=365) #no me complicare le aplicare 365 dia para el año completo y un dia de mas para que no se corte por diferencia horaria entre servidores
        end = now + timedelta(days=1)

        deals_today = mt5.history_deals_get(start, end)
        if deals_today is None:
            err = mt5.last_error()
            logging.error(f"No se pudieron obtener operaciones: {err}")
            return {
                "total_operaciones": 0,
                "ganadoras": 0,
                "perdedoras": 0,
                "ratio_ganadoras": "0%",
                "beneficio_total": 0,
                "promedio_por_operacion": 0,
                "balance": 0,
                "equity": 0,
                "margin": 0,
                "error": f"No se pudieron obtener operaciones: {err}",
            }

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
            "ratio_ganadoras": f"{ratio*2}%",
            "beneficio_total": round(total_profit, 2),
            "promedio_por_operacion": promedio,
            "balance": balance,
            "equity": equity,
            "margin": margin,
        }

    except Exception as e:
        logging.error(f"Error inesperado en obtener_estadistica_dia: {e}")
        return {
            "total_operaciones": 0,
            "ganadoras": 0,
            "perdedoras": 0,
            "ratio_ganadoras": "0%",
            "beneficio_total": 0,
            "promedio_por_operacion": 0,
            "balance": 0,
            "equity": 0,
            "margin": 0,
            "error": f"Error inesperado: {e}",
        }


def operaciones_abiertas():
    positions = mt5.positions_get()
    return [p._asdict() for p in positions] if positions else []


# ===========================================
# 🔹 Monitor de solicitudes
# ===========================================
solicitudes_totales = 0
solicitudes_por_minuto = 0
ping_historial = []
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
            log_solicitudes.append(
                {
                    "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "endpoint": request.path,
                    "metodo": request.method,
                    "ip": request.remote_addr,
                }
            )
            if len(log_solicitudes) > 500:
                log_solicitudes.pop(0)


# ===========================================
# 🌐 ENDPOINTS MT5
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
    start = now - timedelta(days=365)
    end = now + timedelta(days=1)
    deals = mt5.history_deals_get(start, end)
    if deals is None:
        err = mt5.last_error()
        logging.error(f"No se pudieron obtener las órdenes: {err}")
        return jsonify({"error": "No se pudieron obtener las órdenes", "codigo": err})
    daytrade = [d._asdict() for d in deals if d.type != 2]
    return jsonify(daytrade)


# ===========================================
# 🌐 MONITOR CON PING REAL
# ===========================================
@app.route("/monitor")
def monitor():
    global ping_historial
    # Recibido desde la interfaz (ping real se mide en Tkinter)
    with lock:
        return jsonify(
            {
                "estado": "Conectado",
                "solicitudes_por_minuto": solicitudes_por_minuto,
                "solicitudes_totales": solicitudes_totales,
                "log_solicitudes": log_solicitudes[-10:],
            }
        )


def obtener_ip_publica():
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        return response.json()["ip"]
    except requests.RequestException:
        return "IP pública no disponible"


mi_ip_publica = obtener_ip_publica()


# ===========================================
# 🟢 Interfaz gráfica Tkinter
# ===========================================
def iniciar_interfaz():
    root = tk.Tk()
    root.title("Monitor MT5")

    lbl_estado = tk.Label(root, text="Estado: ---")
    lbl_estado.pack()
    lbl_ip = tk.Label(root, text=f"IP Pública: {mi_ip_publica} (para su API)", fg="red", cursor="hand2", font=("Arial", 9, "bold"))
    lbl_ip.pack(pady=5)
    # Función para copiar la IP al portapapeles
    def copiar_ip(event=None):
        root.clipboard_clear()
        root.clipboard_append(mi_ip_publica)
        lbl_ip.config(text=f"IP Pública: {mi_ip_publica} (copiada!)")

    lbl_ip.bind("<Button-1>", copiar_ip)  # Clic para copiar
    lbl_solicitudes = tk.Label(root, text="Solicitudes/minuto: ---")
    lbl_solicitudes.pack()
    lbl_totales = tk.Label(root, text="Solicitudes totales: ---")
    lbl_totales.pack()

    tk.Label(root, text="Últimas solicitudes:").pack()
    txt_log = tk.Text(root, height=10, width=80)
    txt_log.pack()

    def actualizar():
        try:
            start = time.time()
            resp = requests.get(
                "http://127.0.0.1:5000/monitor",
                headers={"X-Internal-Ping": "true"},
                timeout=2,
            )
            ping_real = round((time.time() - start) * 1000, 2)

            # Guardar histórico
            with lock:
                ping_historial.append(ping_real)
                if len(ping_historial) > 100:
                    ping_historial.pop(0)

            data = resp.json()
            lbl_estado.config(text=f"Estado: {data['estado']}", foreground="green")

            lbl_solicitudes.config(
                text=f"Solicitudes/minuto: {data['solicitudes_por_minuto']}"
            )
            lbl_totales.config(
                text=f"Solicitudes totales: {data['solicitudes_totales']}"
            )
            txt_log.delete(1.0, tk.END)
            for entrada in data["log_solicitudes"]:
                txt_log.insert(
                    tk.END,
                    f"{entrada['hora']} | {entrada['ip']} | {entrada['metodo']} | {entrada['endpoint']}\n",
                )
        except:
            lbl_estado.config(text="Estado: 🔴 Desconectado", foreground="red")

            lbl_solicitudes.config(text="Solicitudes/minuto: ---")
            lbl_totales.config(text="Solicitudes totales: ---")
            txt_log.delete(1.0, tk.END)
            txt_log.insert(tk.END, "---")
        root.after(2000, actualizar)

    actualizar()
    root.mainloop()


# ===========================================
# 🟢 Icono bandeja (opcional)
# ===========================================
def create_icon():
    image = Image.new("RGB", (64, 64), "green")
    draw = ImageDraw.Draw(image)
    draw.ellipse((16, 16, 48, 48), fill="white")
    return image


def iniciar_icono():
    icon = pystray.Icon("MT5 Server", create_icon(), "Servidor Flask activo ✅")
    icon.run()


# ===========================================
# ▶️ EJECUCIÓN PRINCIPAL
# ===========================================
def iniciar_servidor():
    serve(app, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    threading.Thread(target=iniciar_servidor, daemon=True).start()
    time.sleep(1)
    iniciar_interfaz()
