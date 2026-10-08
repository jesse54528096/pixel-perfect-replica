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
import html, urllib.request, urllib.error
from decimal import Decimal

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
CITY = {"TPE": "台北", "TYO": "東京", "SEL": "首爾"}
SITE_URL = "https://pixel-perfect-replica-phi-tan.vercel.app"
_hist = boto3.resource("dynamodb").Table("notification_history")
_resend = None


class Transient(Exception):
    pass


def resend_cfg():
    global _resend
    if _resend is None:
        _resend = json.loads(_sm.get_secret_value(SecretId="flight/resend")["SecretString"])
    return _resend


def route_name(route):
    o, d = route.split("-")
    return f"{CITY.get(o, o)} → {CITY.get(d, d)}"


def render(msg):
    name, end = route_name(msg["route"]), msg.get("current_period_end_date") or ""
    if msg["event_type"] == "welcome":
        subj = f"✈️ 訂閱成功：{name} 機票降價通知已開通"
        lines = [f"感謝訂閱！{name} 的降價通知已經開通。",
                 f"月費 NT${int(msg.get('amount') or 0):,}，每月自動扣款；目前有效至 {end}。",
                 "票價達到你的目標價時，我們會寄信通知你。"]
    else:
        subj = f"已取消訂閱：{name} 機票降價通知"
        lines = [f"你已取消 {name} 的降價通知訂閱，之後不會再扣款。",
                 f"已付費的期間內仍會繼續通知，直到 {end}。",
                 "想再追蹤時，隨時可以回來重新訂閱。"]
    text_body = "\n".join(lines + ["", f"管理訂閱：{SITE_URL}/app"])
    e = html.escape
    html_body = ('<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;color:#111">'
                 f'<h2 style="margin:0 0 12px">{e(subj)}</h2>'
                 + "".join(f'<p style="margin:0 0 8px">{e(l)}</p>' for l in lines)
                 + f'<a href="{SITE_URL}/app" style="display:inline-block;margin-top:12px;background:#2563eb;color:#fff;'
                   'padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:bold">管理訂閱</a></div>')
    return subj, html_body, text_body


def send_email(to, subj, html_body, text_body):
    cfg = resend_cfg()
    payload = {"from": cfg["from"], "to": to, "subject": subj, "html": html_body, "text": text_body}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode(),
                                 headers={"Authorization": "Bearer " + cfg["api_key"],
                                          "Content-Type": "application/json", "User-Agent": UA}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, r.status, r.read().decode()
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode()
        if ex.code == 429 or ex.code >= 500:
            raise Transient(f"resend {ex.code} {detail}")
        return False, ex.code, detail
    except urllib.error.URLError as ex:
        raise Transient(f"resend network error {ex}")


def process(msg):
    kind = msg.get("event_type")
    if kind not in ("welcome", "cancel"):
        print(f"unknown event_type {kind}: dropped")
        return
    pk = f"status#{msg['email']}#{msg['route']}#{kind}"
    sk = msg.get("merchant_trade_no") or "-"
    if _hist.get_item(Key={"pk": pk, "sent_at": sk}).get("Item"):
        print(f"{pk} {sk} already sent: skipped")
        return
    subj, html_body, text_body = render(msg)
    sent, code, detail = send_email(msg["email"], subj, html_body, text_body)
    if not sent:
        print(f"{pk} RESEND_DROP {code} {detail}")
        return
    _hist.put_item(Item={"pk": pk, "sent_at": sk, "email": msg["email"], "route": msg["route"],
                         "event_type": kind, "delivered_at": now_utc().strftime(TS_FMT)})
    print(f"{pk} {sk} RESEND_OK {code} {detail}")


def handler(event, context):
    for rec in event.get("Records", []):
        process(json.loads(rec["body"]))
    return {"ok": True}
