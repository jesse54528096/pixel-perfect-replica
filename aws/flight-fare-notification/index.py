import json, os, html, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
CITY = {"TPE": "台北", "TYO": "東京", "SEL": "首爾", "LON": "倫敦", "BKK": "曼谷"}
FLOOR_HOURS = float(os.environ.get("NOTIFY_FLOOR_HOURS", "24"))
REALERT_PCT = float(os.environ.get("REALERT_PCT", "20"))
REALERT_ABS_TWD = float(os.environ.get("REALERT_ABS_TWD", "2000"))

_sm = boto3.client("secretsmanager")
_hist = boto3.resource("dynamodb").Table("notification_history")
_resend = None


def resend_cfg():
    global _resend
    if _resend is None:
        _resend = json.loads(_sm.get_secret_value(SecretId="flight/resend")["SecretString"])
    return _resend


# ---------- renderer (inline; no shared email_render module) ----------

def _cities(route):
    o, d = route.split("-")
    return CITY.get(o, o), CITY.get(d, d), o, d


def _ddmm(iso):
    return iso[8:10] + iso[5:7] if iso and len(iso) >= 10 else ""


def booking_url(fare, marker=None):
    o, d = fare["route"].split("-")
    url = f"https://www.aviasales.com/search/{o}{_ddmm(fare.get('depart_date'))}{d}{_ddmm(fare.get('return_date'))}1"
    return f"{url}?marker={marker}" if marker else url


def subject(fare):
    oc, dc, _, _ = _cities(fare["route"])
    return f"✈️ {oc} → {dc} 降價通知！NT${fare['price']:,} 已達標"


def render_text(fare, target_price, marker=None, usd_price=None):
    oc, dc, _, _ = _cities(fare["route"])
    lines = [f"{oc} → {dc} 降價通知", "",
             f"目前最低價：NT${fare['price']:,}"]
    if usd_price is not None:
        lines.append(f"（約 US${usd_price:,}）")
    lines += [f"你的目標價：NT${target_price:,}",
              f"航空公司：{fare.get('airline') or '-'}",
              f"去程：{(fare.get('depart_date') or '')[:10]}　回程：{(fare.get('return_date') or '')[:10]}",
              "", f"立即訂購：{booking_url(fare, marker)}"]
    return "\n".join(lines)


def render_html(fare, target_price, marker=None, usd_price=None):
    oc, dc, _, _ = _cities(fare["route"])
    usd = (f'<p style="margin:0 0 16px;color:#555;font-size:14px">約 US${usd_price:,}</p>'
           if usd_price is not None else "")
    e = html.escape
    return (
        '<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;color:#111">'
        f'<h2 style="margin:0 0 8px">{e(oc)} → {e(dc)} 降價通知</h2>'
        f'<p style="margin:0 0 4px;font-size:28px;font-weight:bold">NT${fare["price"]:,}</p>'
        f'{usd}'
        f'<p style="margin:0 0 4px">你的目標價：NT${target_price:,}</p>'
        f'<p style="margin:0 0 4px">航空公司：{e(str(fare.get("airline") or "-"))}</p>'
        f'<p style="margin:0 0 20px">去程 {e((fare.get("depart_date") or "")[:10])}　'
        f'回程 {e((fare.get("return_date") or "")[:10])}</p>'
        f'<a href="{e(booking_url(fare, marker))}" style="display:inline-block;background:#2563eb;color:#fff;'
        'padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:bold">立即訂購</a>'
        '<p style="margin:24px 0 0;color:#888;font-size:12px">票價可能隨時變動，以訂購頁面為準。</p>'
        '</div>'
    )


# ---------- dedup ----------

def last_alert(pk):
    items = _hist.query(KeyConditionExpression=Key("pk").eq(pk), ScanIndexForward=False, Limit=1).get("Items", [])
    return items[0] if items else None


def should_send(last, new_price, now):
    if not last:
        return True, "first alert"
    sent = datetime.fromisoformat(last["sent_at"])
    if now - sent >= timedelta(hours=FLOOR_HOURS):
        return True, "outside floor window"
    prev = float(last["price"])
    if new_price <= prev * (1 - REALERT_PCT / 100) or (prev - new_price) >= REALERT_ABS_TWD:
        return True, f"big drop from {prev:.0f}"
    return False, f"last alert {last['sent_at']} at {prev:.0f}"


# ---------- send ----------

class Transient(Exception):
    pass


def send_email(to, subj, html_body, text_body):
    cfg = resend_cfg()
    payload = {"from": cfg["from"], "to": to, "subject": subj, "html": html_body, "text": text_body}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(payload).encode(),
                                 headers={"Authorization": "Bearer " + cfg["api_key"],
                                          "Content-Type": "application/json", "User-Agent": UA},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, r.status, r.read().decode()
    except urllib.error.HTTPError as ex:
        detail = ex.read().decode()
        if ex.code == 429 or ex.code >= 500:
            raise Transient(f"resend {ex.code} {detail}")
        return False, ex.code, detail  # permanent (403/422/...): drop, don't redeliver
    except urllib.error.URLError as ex:
        raise Transient(f"resend network error {ex}")


def process(msg):
    email, route = msg["email"], msg["route"]
    tw = msg["cheapest"]
    fare = dict(tw, route=route)
    price = int(tw["price"])
    target = int(msg.get("target_price", 0))
    usd_price = msg.get("cheapest_usd", {}).get("price") if msg.get("cheapest_usd") else None
    pk = f"{email}#{route}"
    now = datetime.now(timezone.utc)

    ok, why = should_send(last_alert(pk), price, now)
    if not ok:
        print(f"{pk} NT${price} skipped (deduped): {why}")
        return
    sent, code, detail = send_email(email, subject(fare), render_html(fare, target, usd_price=usd_price),
                                    render_text(fare, target, usd_price=usd_price))
    if not sent:
        print(f"{pk} RESEND_DROP {code} {detail}")
        return
    _hist.put_item(Item={"pk": pk, "sent_at": now.isoformat(), "email": email, "route": route,
                         "price": Decimal(price), "currency": "TWD"})
    print(f"{pk} NT${price} sent ({why}) RESEND_OK {code} {detail}")


def handler(event, context):
    for rec in event.get("Records", []):
        process(json.loads(rec["body"]))
    return {"ok": True}
