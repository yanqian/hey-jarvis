# Pipeline guide

The pipeline is Hey Jarvis’s default backend:

```text
WAIT_WAKE → ACK_PLAYING → ARMED → RECORDING → TRANSCRIBE
          → ASK_OPENAI/tool → TTS → PLAYING → WAIT_WAKE
```

It is the best path for inspecting each boundary independently.

## Interaction

Start with:

```bash
python -m src.main
```

Say “Hey Jarvis”, wait for the acknowledgement, then ask a question. ARMED
requires sustained local speech and preserves bounded pre-roll. No speech,
unusable recordings, empty/filler transcripts, and local cancellation phrases
return quietly to wake listening without generating an answer.

After answer playback or local cancellation, the assistant suppresses residual
wake detections and waits for observed quiet before becoming wake-ready again.

## Answer routing

`ENABLE_TOOLS=1` routes deterministic and realtime-sensitive requests before
general chat:

- local time and safe arithmetic run locally;
- weather uses Open-Meteo;
- FX uses Frankfurter reference rates;
- stock quotes use Finnhub with `FINNHUB_API_KEY`;
- unsupported live categories such as news or sports scores are refused rather
  than guessed from model memory.

Inspect routing without audio:

```bash
python -m src.main --text "现在几点"
python -m src.main --text "一百乘以一千等于多少"
python -m src.main --text "明天天气怎么样"
python -m src.main --text "100 USD to SGD"
python -m src.main --text "AAPL stock price"
python -m src.main --text "今天有什么新闻"
```

The calculator is a bounded parser and is never executed with `eval`.
Provider results include source/freshness/caveat data. OpenAI naturalization may
improve spoken wording but cannot replace the structured result; failures do
not fall through to speculative chat.

## Knowledge and response language

Ordinary historical, linguistic, scientific, and other stable questions use
the chat model’s available knowledge. This path does not browse the web and
must not claim that sources or current facts were checked. Genuine uncertainty
should be stated briefly while still giving useful context.

The current request controls the reply language independently of prior turns.
Chinese input receives concise Simplified Chinese; English receives English.
Translation, spelling, terminology, pronunciation, and explicit response-
language requests may include the requested target language.

## Timing

Successful loops emit ordered `pipeline_timing` records and one
`response_timing` summary. The summary includes recording, transcription,
answer/tool routing, TTS, `ready_to_play`, playback, post-recording total, and
route durations.

These are monotonic elapsed durations for diagnosis. They do not include answer
text, raw audio, or credentials and do not make the serial pipeline faster by
themselves.

## Offline verification

```bash
python -m src.main --dry-run
python -m src.main --fake-backend
python -m src.main --text "2 + 2"
```

The fake backend exercises the complete state transition without microphone,
speakers, network, OpenAI, or provider calls.

Audio and cancellation tuning live in
[Configuration](CONFIGURATION.md). Device symptoms live in
[Troubleshooting](TROUBLESHOOTING.md). Detailed real-device scenarios remain in
[Manual testing](../MANUAL_TESTING.md).
