# REST API: MetaTrade5

Esta colección te permite interactuar con los principales endpoints de MetaTrade5 para consultar balance, operaciones abiertas y operaciones del día.

## Endpoints disponibles

### 1\. Balance

- Método: GET
    
- Ruta: `{{base_url}}/api/balance`
    
- Descripción: Devuelve el estado financiero de la cuenta (balance actual, equity, margen, totales y métricas de rendimiento).
    
- Ejemplo de respuesta:
    
    ``` json
          {
          "balance": 1006126.22,
          "beneficio_total": 6126.22,
          "equity": 941826.22,
          "ganadoras": 92,
          "margin": 991576.5,
          "perdedoras": 12,
          "promedio_por_operacion": 28.76,
          "ratio_ganadoras": "86.38%",
          "total_operaciones": 213
          }
    
     ```
    

### 2\. Daytrade

- Método: GET
    
- Ruta: `{{base_url}}/api/daytrade`
    
- Descripción: Devuelve las operaciones realizadas durante el día con detalles como ticket, símbolo, precio y ganancia.
    
- Ejemplo de respuesta:
    
    ``` json
          [
          {
            "comment": "",
            "commission": 0.0,
            "entry": 0,
            "external_id": "",
            "fee": 0.0,
            "magic": 0,
            "order": 5472953080,
            "position_id": 5472953080,
            "price": 1.15174,
            "profit": 0.0,
            "reason": 0,
            "swap": 0.0,
            "symbol": "EURUSD",
            "ticket": 5130856543,
            "time": 1762182254,
            "time_msc": 1762182254260,
            "type": 0,
            "volume": 1.0
          }
          ]
    
     ```
    

### 3\. Opentrader

- Método: GET
    
- Ruta: `{{base_url}}/api/opentrader`
    
- Descripción: Devuelve las operaciones abiertas actualmente, incluyendo símbolo, precio de apertura, precio actual, volumen y ganancia/pérdida.
    
- Ejemplo de respuesta:
    
    ``` json
          [
          {
            "ticket": 5503415775,
            "symbol": "XAUUSD",
            "price_current": 3965.01,
            "price_open": 3966.3,
            "profit": -12900.0,
            "volume": 100.0,
            "time": 1762345310
          }
          ]
    
     ```
    

---
