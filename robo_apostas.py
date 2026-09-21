import os, math, itertools, requests
from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY = os.environ["API_FOOTBALL_KEY"]
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BASE = "https://v3.football.api-sports.io"
TZ = "America/Sao_Paulo"

# Configurações principais
ODD_MIN = 100.0
ODD_MAX = 150.0
MIN_SCORE = 72.0
MAX_LEGS = 12
TOP_FIXTURES = 24

def api(path, params=None):
    r = requests.get(
        BASE + path,
        headers={"x-apisports-key": API_KEY},
        params=params or {},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise RuntimeError(str(data["errors"]))
    return data.get("response", [])

def get_bet365_id():
    rows = api("/odds/bookmakers", {"search": "bet365"})
    return rows[0].get("id") if rows else None

def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def prediction_for(fixture_id):
    rows = api("/predictions", {"fixture": fixture_id})
    return rows[0] if rows else None

def flatten_odds(row):
    result = []
    for bookmaker in row.get("bookmakers", []):
        for bet in bookmaker.get("bets", []):
            market = str(bet.get("name", ""))
            for value in bet.get("values", []):
                odd = num(value.get("odd"))
                if 1.01 < odd <= 8:
                    result.append(
                        (market, str(value.get("value", "")), odd)
                    )
    return result

def build_candidates(fixture, bookmaker_id):
    fixture_id = fixture["fixture"]["id"]
    prediction = prediction_for(fixture_id)
    if not prediction:
        return []

    p = prediction.get("predictions", {})
    percent = p.get("percent", {})
    home = fixture["teams"]["home"]["name"]
    away = fixture["teams"]["away"]["name"]

    probabilities = {
        home: num(percent.get("home")),
        "Draw": num(percent.get("draw")),
        away: num(percent.get("away")),
    }

    odds_rows = api(
        "/odds",
        {"fixture": fixture_id, "bookmaker": bookmaker_id},
    )
    if not odds_rows:
        return []

    candidates = []
    for market, value, odd in flatten_odds(odds_rows[0]):
        probability = 0.0
        market_lower = market.lower()

        # Mercados em que a API fornece uma probabilidade diretamente.
        if market_lower in ("match winner", "1x2"):
            probability = probabilities.get(value, 0.0)

        elif market_lower == "double chance":
            if value == "Home/Draw":
                probability = probabilities[home] + probabilities["Draw"]
            elif value == "Draw/Away":
                probability = probabilities["Draw"] + probabilities[away]
            elif value == "Home/Away":
                probability = probabilities[home] + probabilities[away]

        # Não inventamos probabilidade para mercados que o modelo da API
        # não quantifica de forma comparável.
        if probability <= 0:
            continue

        implied = 100.0 / odd
        edge = probability - implied

        # Score heurístico: favorece probabilidade do modelo acima da
        # probabilidade implícita. Não é uma garantia de acerto.
        score = min(100.0, max(0.0, 55.0 + edge * 1.8))

        if score >= MIN_SCORE:
            candidates.append(
                {
                    "fixture_id": fixture_id,
                    "home": home,
                    "away": away,
                    "market": market,
                    "value": value,
                    "odd": odd,
                    "prob": probability,
                    "edge": edge,
                    "score": score,
                }
            )

    return candidates

def compatible(a, b):
    # Não permite duas seleções do mesmo jogo.
    return a["fixture_id"] != b["fixture_id"]

def choose_combo(candidates):
    candidates = sorted(
        candidates,
        key=lambda item: item["score"],
        reverse=True,
    )[:18]

    best = None

    for n in range(6, min(MAX_LEGS, len(candidates)) + 1):
        for combo in itertools.combinations(candidates, n):
            if any(
                not compatible(combo[i], combo[j])
                for i in range(n)
                for j in range(i + 1, n)
            ):
                continue

            odd = math.prod(item["odd"] for item in combo)
            if not (ODD_MIN <= odd <= ODD_MAX):
                continue

            score = sum(item["score"] for item in combo) / n
            # Pequena preferência por ficar perto de 100–120,
            # sem sacrificar o score.
            closeness = max(0.0, 10.0 - abs(odd - 110.0) / 10.0)
            total = score + closeness

            if best is None or total > best[0]:
                best = (total, odd, combo, score)

        if best and best[1] <= 125:
            break

    return best

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": CHAT_ID, "text": message},
        timeout=20,
    )
    response.raise_for_status()

def main():
    now = datetime.now(ZoneInfo(TZ))
    date = now.strftime("%Y-%m-%d")

    fixtures = api(
        "/fixtures",
        {"date": date, "timezone": TZ},
    )

    upcoming = []
    for fixture in fixtures:
        status = fixture.get("fixture", {}).get("status", {}).get("short")
        if status not in {"NS", "TBD"}:
            continue

        timestamp = fixture.get("fixture", {}).get("timestamp")
        if timestamp:
            upcoming.append(fixture)

    upcoming.sort(
        key=lambda item: item["fixture"]["timestamp"]
    )
    upcoming = upcoming[:TOP_FIXTURES]

    bookmaker_id = get_bet365_id()

    if not bookmaker_id:
        send_telegram(
            "🤖 Robô\n"
            "Não encontrei a Bet365 na base de odds da API hoje.\n"
            "Nenhum cupom foi gerado."
        )
        return

    candidates = []

    for fixture in upcoming:
        try:
            candidates.extend(
                build_candidates(fixture, bookmaker_id)
            )
        except Exception:
            # Um jogo com dados incompletos não derruba o robô inteiro.
            continue

    result = choose_combo(candidates)

    if not result:
        send_telegram(
            f"🤖 Robô — {now:%d/%m/%Y %H:%M}\n\n"
            "Nenhuma combinação passou pelos filtros para chegar "
            "a uma odd 100+.\n\n"
            "Não vou forçar uma aposta."
        )
        return

    _, odd, combo, score = result

    lines = [
        "⚽ CUPOM ANALISADO",
        "",
        f"Odd estimada: {odd:.2f}",
        f"Score médio do modelo: {score:.1f}/100",
        "",
    ]

    for i, item in enumerate(combo, 1):
        lines.append(
            f"{i}. {item['home']} x {item['away']}"
        )
        lines.append(
            f"   {item['market']} — {item['value']} @ {item['odd']:.2f}"
        )
        lines.append(
            f"   Modelo: {item['prob']:.1f}% | "
            f"implícita: {100.0 / item['odd']:.1f}%"
        )

    lines.extend(
        [
            "",
            "⚠️ Odds podem mudar antes da confirmação.",
            "⚠️ A probabilidade é uma estimativa do modelo.",
            "⚠️ O robô NÃO realiza a aposta automaticamente.",
        ]
    )

    send_telegram("\n".join(lines))

if __name__ == "__main__":
    main()
