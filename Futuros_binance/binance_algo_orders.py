import hmac
import os
import time
from hashlib import sha256
from urllib.parse import urlencode

import requests


BASE_URL = "https://fapi.binance.com"


def _get_keys():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("Faltan BINANCE_API_KEY o BINANCE_API_SECRET para usar Algo Orders.")
    return api_key, api_secret


def _signed_request(method: str, path: str, params: dict | None = None):
    api_key, api_secret = _get_keys()
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    params.setdefault("recvWindow", 5000)
    query = urlencode(params, doseq=True)
    signature = hmac.new(api_secret.encode(), query.encode(), sha256).hexdigest()
    signed_params = dict(params)
    signed_params["signature"] = signature

    url = f"{BASE_URL}{path}"
    headers = {"X-MBX-APIKEY": api_key}
    if method == "GET":
        resp = requests.request(method, url, headers=headers, params=signed_params)
    else:
        resp = requests.request(method, url, headers=headers, data=signed_params)
    resp.raise_for_status()
    return resp.json()


def place_conditional_stop_market(client, symbol: str, side: str, stop_price: float, qty_str: str, positionSide: str = "BOTH"):
    """
    Crea un Algo Order CONDITIONAL STOP_MARKET para freno nativo.
    Devuelve la respuesta completa (incluye algoId / clientAlgoId).
    """
    payload = {
        "algoType": "CONDITIONAL",
        "symbol": symbol,
        "side": side,
        "type": "STOP_MARKET",
        "triggerPrice": f"{stop_price:.2f}",
        "quantity": qty_str,
        "positionSide": positionSide,
        "reduceOnly": "true",
    }
    print("[FRENO NATIVO ALGO] Intentando STOP_MARKET", side, "triggerPrice", payload["triggerPrice"], "qty", qty_str)
    resp = _signed_request("POST", "/fapi/v1/algoOrder", payload)
    print("[FRENO NATIVO ALGO] OK Binance:", resp)
    try:
        open_algo = get_open_algo_orders(client, symbol)
        print(f"[FRENO NATIVO ALGO] Open algo orders ({len(open_algo)}):", open_algo)
        if not open_algo:
            print("⚠️ [FRENO NATIVO ALGO] WARNING: STOP condicional no aparece en openAlgoOrders.")
    except Exception as e:
        print(f"⚠️ [FRENO NATIVO ALGO] No se pudieron leer openAlgoOrders: {e}")
    return resp


def get_open_algo_orders(client, symbol: str):
    params = {"symbol": symbol}
    return _signed_request("GET", "/fapi/v1/openAlgoOrders", params)


def cancel_algo_order(client, symbol: str, algoId=None, clientAlgoId=None):
    params = {"symbol": symbol}
    if algoId is not None:
        params["algoId"] = algoId
    if clientAlgoId is not None:
        params["clientAlgoId"] = clientAlgoId
    return _signed_request("DELETE", "/fapi/v1/algoOrder", params)


def cancel_all_open_algo_orders(client, symbol: str):
    params = {"symbol": symbol}
    return _signed_request("DELETE", "/fapi/v1/algoOpenOrders", params)
