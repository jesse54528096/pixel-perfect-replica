# ---------- shared ECPay helpers (folded into each single-file Lambda) ----------
import base64, hashlib, json, urllib.parse
from datetime import datetime, timedelta, timezone
import boto3

TS_FMT = "%Y-%m-%dT%H:%M:%SZ"  # fixed-width UTC; current_period_end is compared as a string
_sm = boto3.client("secretsmanager")
_ecpay = None


def ecpay_cfg():
    global _ecpay
    if _ecpay is None:
        _ecpay = json.loads(_sm.get_secret_value(SecretId="flight/ecpay")["SecretString"])
    return _ecpay


def ecpay_host():
    return "https://payment.ecpay.com.tw" if ecpay_cfg().get("env") == "prod" else "https://payment-stage.ecpay.com.tw"


def ecpay_url_encode(s):
    e = urllib.parse.quote_plus(str(s)).replace("~", "%7E").lower()
    for o, n in (("%2d", "-"), ("%5f", "_"), ("%2e", "."), ("%21", "!"), ("%2a", "*"), ("%28", "("), ("%29", ")")):
        e = e.replace(o, n)
    return e


def gen_cmv(params, hash_key, hash_iv):
    items = {k: v for k, v in params.items() if k != "CheckMacValue"}  # keep "" values
    body = "&".join(f"{k}={items[k]}" for k in sorted(items, key=str.lower))
    raw = f"HashKey={hash_key}&{body}&HashIV={hash_iv}"
    return hashlib.sha256(ecpay_url_encode(raw).encode()).hexdigest().upper()


def verify_cmv(params):
    cfg = ecpay_cfg()
    return params.get("CheckMacValue", "").upper() == gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])


def form_params(event):
    raw = (event or {}).get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}


def text(body, status=200):
    return {"statusCode": status, "headers": {"Content-Type": "text/plain; charset=utf-8"}, "body": body}


def now_utc():
    return datetime.now(timezone.utc)


def add_period(start, period_type="M", frequency=1):
    n = max(int(frequency or 1), 1)
    if period_type == "D":
        return start + timedelta(days=n)
    if period_type == "Y":
        return start.replace(year=start.year + n)
    m = start.month - 1 + n
    y, m = start.year + m // 12, m % 12 + 1
    for day in (start.day, 30, 29, 28):
        try:
            return start.replace(year=y, month=m, day=day)
        except ValueError:
            continue


def taipei_date(dt):
    return (dt + timedelta(hours=8)).strftime("%Y-%m-%d")
import os

SITE_URL = os.environ["SITE_URL"].strip().rstrip("/")


def handler(event, context):
    # Browser return from ECPay (a POST). UX only: never activates anything; ReturnURL does that.
    p = form_params(event) if (event or {}).get("body") else {}
    outcome = "success" if p.get("RtnCode", "1") == "1" else "failed"
    print(f"OrderResultURL {p.get('MerchantTradeNo', '-')} RtnCode={p.get('RtnCode', '-')} -> {outcome}")
    return {"statusCode": 302, "headers": {"Location": f"{SITE_URL}/app?purchase={outcome}"}, "body": ""}
