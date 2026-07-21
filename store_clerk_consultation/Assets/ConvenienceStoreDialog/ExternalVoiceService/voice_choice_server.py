from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse
import json
import re
import time


HOST = "127.0.0.1"
PORT = 8765

SESSIONS = {
    "default": {
        "version": 0,
        "choice": -1,
        "transcript": "",
        "confidence": 0.0,
    }
}


CHOICE_RULES = [
    (
        0,
        [
            "唐揚げ",
            "からあげ",
            "弁当",
            "温めて",
            "温め",
            "袋はいりません",
            "いりません",
            "suica",
            "スイカ",
            "もう一度",
            "練習",
        ],
    ),
    (
        1,
        [
            "コーヒー",
            "珈琲",
            "現金",
            "袋をお願いします",
            "袋お願いします",
            "ありがとうございます",
            "他の商品",
        ],
    ),
    (
        2,
        [
            "atm",
            "エーティーエム",
            "袋も",
            "箸",
            "はし",
            "クレジット",
            "終了",
            "ありません",
        ],
    ),
]


def normalize(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("　", " ")
    text = re.sub(r"[。．、，！？!?「」『』（）()［］\[\]\s]+", "", text)
    return text


def match_choice(transcript: str) -> tuple[int, float]:
    normalized = normalize(transcript)
    if not normalized:
        return -1, 0.0

    best_choice = -1
    best_score = 0

    for choice, keywords in CHOICE_RULES:
        score = 0
        for keyword in keywords:
            if normalize(keyword) in normalized:
                score += len(normalize(keyword))

        if score > best_score:
            best_choice = choice
            best_score = score

    if best_choice < 0:
        return -1, 0.0

    confidence = min(0.99, 0.55 + best_score / 20.0)
    return best_choice, confidence


def update_session(session_id: str, transcript: str, forced_choice: int | None = None) -> dict:
    state = SESSIONS.setdefault(
        session_id,
        {
            "version": 0,
            "choice": -1,
            "transcript": "",
            "confidence": 0.0,
        },
    )

    if forced_choice is None:
        choice, confidence = match_choice(transcript)
    else:
        choice = forced_choice
        confidence = 1.0

    state["version"] = int(time.time() * 1000)
    state["choice"] = choice
    state["transcript"] = transcript
    state["confidence"] = confidence
    return state


def payload_for(state: dict) -> str:
    transcript = str(state["transcript"]).replace("|", " ").replace("\r", " ").replace("\n", " ")
    return f'{state["version"]}|{state["choice"]}|{transcript}|{state["confidence"]:.2f}'


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]

        if parsed.path == "/":
            self.send_html()
            return

        if len(parts) >= 3 and parts[0] == "session":
            session_id = parts[1]
            action = parts[2]
            query = parse_qs(parsed.query)

            if action == "latest":
                state = SESSIONS.setdefault(
                    session_id,
                    {"version": 0, "choice": -1, "transcript": "", "confidence": 0.0},
                )
                self.send_text(payload_for(state))
                return

            if action == "simulate":
                transcript = query.get("text", [""])[0]
                state = update_session(session_id, unquote(transcript))
                self.send_text(payload_for(state))
                return

            if action == "choice":
                transcript = query.get("text", ["manual choice"])[0]
                try:
                    choice = int(query.get("choice", ["-1"])[0])
                except ValueError:
                    choice = -1
                state = update_session(session_id, unquote(transcript), choice)
                self.send_text(payload_for(state))
                return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) < 3 or parts[0] != "session":
            self.send_response(404)
            self.end_headers()
            return

        session_id = parts[1]
        action = parts[2]
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""

        transcript = ""
        forced_choice = None

        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type and raw:
            body = json.loads(raw)
            transcript = str(body.get("text", ""))
            if "choice" in body:
                forced_choice = int(body["choice"])
        elif raw:
            fields = parse_qs(raw)
            transcript = fields.get("text", [raw])[0]
            if "choice" in fields:
                forced_choice = int(fields["choice"][0])

        if action == "transcript":
            state = update_session(session_id, transcript)
            self.send_text(payload_for(state))
            return

        if action == "choice":
            state = update_session(session_id, transcript, forced_choice if forced_choice is not None else -1)
            self.send_text(payload_for(state))
            return

        self.send_response(404)
        self.end_headers()

    def send_text(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def send_html(self) -> None:
        body = """
<!doctype html>
<meta charset="utf-8">
<title>Voice Choice Simulator</title>
<h1>Voice Choice Simulator</h1>
<p>Submit recognized Japanese text. VRChat polls <code>/session/default/latest</code>.</p>
<form action="/session/default/simulate" method="get">
  <input name="text" style="width: 420px" value="唐揚げ弁当を探しています">
  <button type="submit">Submit transcript</button>
</form>
<ul>
  <li><a href="/session/default/simulate?text=唐揚げ弁当を探しています">唐揚げ弁当を探しています</a></li>
  <li><a href="/session/default/simulate?text=コーヒーはありますか">コーヒーはありますか</a></li>
  <li><a href="/session/default/simulate?text=ATMはどこですか">ATMはどこですか</a></li>
  <li><a href="/session/default/latest">Latest payload</a></li>
</ul>
"""
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Voice choice server listening at http://{HOST}:{PORT}")
    print("Open http://127.0.0.1:8765/ to simulate ASR text.")
    server.serve_forever()


if __name__ == "__main__":
    main()
