import unittest
from datetime import datetime, timedelta, timezone

from src.tools import answer_with_tools, execute_route, is_realtime_sensitive, route_text
from src.tools.providers import ProviderConfig
from src.tools.router import format_text_debug
from src.openai_client import OpenAIClientError


class FakeJsonClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, *, params=None, timeout_seconds=5.0):
        self.calls.append((url, dict(params or {}), timeout_seconds))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def weather_geocoding_response():
    return {
        "results": [
            {
                "name": "Singapore",
                "country": "Singapore",
                "latitude": 1.29,
                "longitude": 103.85,
                "timezone": "Asia/Singapore",
            }
        ]
    }


def weather_daily_response():
    return {
        "daily": {
            "time": ["2026-07-06", "2026-07-07"],
            "temperature_2m_min": [25.0, 24.0],
            "temperature_2m_max": [32.0, 31.0],
            "apparent_temperature_max": [37.0, 36.0],
            "weather_code": [61, 63],
            "precipitation_sum": [1.0, 3.0],
            "rain_sum": [1.0, 3.0],
            "precipitation_probability_max": [55, 70],
        }
    }


def stock_quote_response():
    return {"c": 193.12, "d": 1.23, "dp": 0.64, "h": 194.0, "l": 190.0, "o": 191.0, "pc": 191.89, "t": 1783306800}


class FakeChatClient:
    def __init__(self):
        self.calls = []

    def ask_chatgpt(self, text, history):
        self.calls.append(text)
        history.append({"role": "user", "content": text})
        history.append({"role": "assistant", "content": "chat answer"})
        return "chat answer"


class FakeNaturalizingClient(FakeChatClient):
    def __init__(self, *, naturalized_answer="naturalized tool answer", fail=False):
        super().__init__()
        self.naturalized_answer = naturalized_answer
        self.fail = fail
        self.naturalization_calls = []

    def naturalize_tool_answer(self, **kwargs):
        self.naturalization_calls.append(kwargs)
        if self.fail:
            raise OpenAIClientError("OpenAI tool answer naturalization request failed: timeout")
        return self.naturalized_answer


class ToolRoutingTests(unittest.TestCase):
    def local_clock(self):
        return datetime(2026, 7, 6, 9, 8, tzinfo=timezone(timedelta(hours=8), name="+08"))

    def test_routes_calculator_and_evaluates_safe_expression(self):
        route = route_text("what is two plus two?")
        result = execute_route(route)

        self.assertEqual(route.category, "calculator")
        self.assertEqual(route.tool_name, "safe_calculator")
        self.assertEqual(route.params["expression"], "2 + 2")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.answer, "The answer is 4.")

    def test_routes_traditional_chinese_local_tool_requests(self):
        for text in ("現在幾點了", "幾點了", "現在時間"):
            with self.subTest(text=text):
                route = route_text(text)
                result = execute_route(route, now_provider=self.local_clock)

                self.assertEqual(route.category, "time")
                self.assertEqual(route.tool_name, "local_time")
                self.assertEqual(result.status, "success")
                self.assertIn("09:08", result.answer)

        route = route_text("100減20是多少")
        result = execute_route(route)

        self.assertEqual(route.category, "calculator")
        self.assertEqual(route.tool_name, "safe_calculator")
        self.assertEqual(route.params["expression"], "100-20")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.answer, "The answer is 80.")

    def test_routes_spoken_chinese_integer_arithmetic(self):
        cases = (
            ("一加一等于几", "1+1", "The answer is 2."),
            ("一加一等於幾", "1+1", "The answer is 2."),
            ("十二加三是多少", "12+3", "The answer is 15."),
            ("一百二十三減二十", "123-20", "The answer is 103."),
            ("一百零二加八", "102+8", "The answer is 110."),
            ("兩千除以十", "2000/10", "The answer is 200."),
        )
        for text, expression, answer in cases:
            with self.subTest(text=text):
                route = route_text(text)
                result = execute_route(route)

                self.assertEqual(route.category, "calculator")
                self.assertEqual(route.tool_name, "safe_calculator")
                self.assertEqual(route.params["expression"], expression)
                self.assertEqual(result.status, "success")
                self.assertEqual(result.answer, answer)

    def test_ambiguous_chinese_digit_sequence_does_not_guess(self):
        route = route_text("一二加三是多少")

        self.assertEqual(route.category, "none")

    def test_rejects_unsafe_calculator_expression(self):
        route = route_text("__import__('os').system('date')")

        self.assertEqual(route.category, "none")

        result = execute_route(route)
        self.assertEqual(result.status, "noop")

    def test_routes_local_time_with_injectable_clock(self):
        route = route_text("现在几点")
        result = execute_route(route, now_provider=self.local_clock)

        self.assertEqual(route.category, "time")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.summary, "local time 2026-07-06 09:08 +08")
        self.assertIn("09:08", result.answer)

    def test_routes_weather_with_location_and_intent(self):
        route = route_text("tomorrow weather in Tokyo")

        self.assertEqual(route.category, "weather")
        self.assertEqual(route.params["intent"], "tomorrow")
        self.assertEqual(route.params["location"], "tokyo")

        chinese_route = route_text("明天东京天气怎么样")
        self.assertEqual(chinese_route.category, "weather")
        self.assertEqual(chinese_route.params["intent"], "tomorrow")
        self.assertEqual(chinese_route.params["location"], "东京")

    def test_weather_relative_location_uses_default_location(self):
        for text in (
            "今天这里天气怎么样",
            "今天这边天气怎么样",
            "今天我这里天气怎么样",
            "本地天气如何",
            "附近天气怎么样",
            "weather nearby",
            "weather in here",
            "weather for current location",
            "weather in the current location",
        ):
            with self.subTest(text=text):
                route = route_text(text)

                self.assertEqual(route.category, "weather")
                self.assertNotIn("location", route.params)

    def test_routes_fx_with_english_and_chinese_aliases(self):
        route = route_text("convert 100 US dollars to Singapore dollars")

        self.assertEqual(route.category, "fx")
        self.assertEqual(route.params["amount"], "100")
        self.assertEqual(route.params["base"], "USD")
        self.assertEqual(route.params["quote"], "SGD")

        chinese_route = route_text("100美元兑人民币汇率是多少")
        self.assertEqual(chinese_route.category, "fx")
        self.assertEqual(chinese_route.params["amount"], "100")
        self.assertEqual(chinese_route.params["base"], "USD")
        self.assertEqual(chinese_route.params["quote"], "CNY")

    def test_routes_fx_with_documented_single_currency_default_shape(self):
        route = route_text("100 SGD exchange rate")

        self.assertEqual(route.category, "fx")
        self.assertEqual(route.params["amount"], "100")
        self.assertEqual(route.params["base"], "SGD")
        self.assertNotIn("quote", route.params)

        unsupported_route = route_text("chf to usd exchange rate")
        self.assertEqual(unsupported_route.category, "fx")
        self.assertEqual(unsupported_route.params["unsupported_currency"], "CHF")
        self.assertEqual(unsupported_route.params["quote"], "USD")

    def test_routes_stock_tickers_and_conservative_aliases(self):
        cases = {
            "苹果股价多少": "AAPL",
            "AAPL stock price": "AAPL",
            "what is Tesla stock price": "TSLA",
        }

        for text, expected_symbol in cases.items():
            with self.subTest(text=text):
                route = route_text(text)
                self.assertEqual(route.category, "stock")
                self.assertEqual(route.params["symbol"], expected_symbol)

    def test_routes_personal_us_watchlist_names(self):
        cases = {
            "阿里巴巴股价": "BABA", "Costco stock price": "COST", "百度股票": "BIDU",
            "富途控股股价": "FUTU", "思愛普股價": "SAP", "Advanced Micro Devices stock price": "AMD",
            "英特爾股票": "INTC", "NVIDIA stock price": "NVDA", "特斯拉股价": "TSLA",
            "微牛股价": "BULL", "Robinhood stock price": "HOOD", "美國運通股價": "AXP",
            "奈飛股票": "NFLX", "沃尔玛股价": "WMT", "甲骨文股票": "ORCL",
            "Grab Holdings stock price": "GRAB", "盈透證券股價": "IBKR", "Microsoft stock price": "MSFT",
            "伯克希爾股價": "BRK.B", "可口可樂股票": "KO", "納斯達克100 ETF股價": "QQQ",
            "冬海集團股價": "SE", "Google stock price": "GOOGL", "Apple stock price": "AAPL",
            "iShares Core S&P 500 股价": "IVV", "標普500 ETF股價": "IVV",
            "拼多多控股股价": "PDD", "阿斯麥股票": "ASML",
            "台積電股價": "TSM", "美光科技股票": "MU", "SpaceX 股价": "SPCX",
        }

        for text, expected_symbol in cases.items():
            with self.subTest(text=text):
                route = route_text(text)
                self.assertEqual(route.category, "stock")
                self.assertEqual(route.params["symbol"], expected_symbol)

    def test_google_names_choose_googl_but_explicit_tickers_take_precedence(self):
        cases = {
            "Google 股价": "GOOGL", "Alphabet stock price": "GOOGL", "谷歌股价": "GOOGL",
            "GOOG 股价": "GOOG", "GOOGL 股价": "GOOGL", "GOOG Google stock price": "GOOG",
        }

        for text, expected_symbol in cases.items():
            with self.subTest(text=text):
                route = route_text(text)
                self.assertEqual(route.category, "stock")
                self.assertEqual(route.params["symbol"], expected_symbol)

    def test_watchlist_names_without_stock_intent_remain_ordinary_chat(self):
        for text in ("苹果怎么样", "SpaceX怎么样", "Costco membership", "我喜欢拼多多"):
            with self.subTest(text=text):
                self.assertEqual(route_text(text).category, "none")

    def test_stock_marker_without_symbol_returns_structured_unknown_symbol_error(self):
        route = route_text("stock market today")
        result = execute_route(route, provider_config=ProviderConfig(finnhub_api_key="fh-secret"))

        self.assertEqual(route.category, "stock")
        self.assertNotIn("symbol", route.params)
        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "stock market provider error: unknown_symbol")

    def test_weather_answer_path_uses_provider_and_skips_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([weather_geocoding_response(), weather_daily_response()])
        history = []

        answer, route, result = answer_with_tools(
            "明天天气怎么样",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertEqual(route.category, "weather")
        self.assertEqual(route.params["intent"], "tomorrow")
        self.assertEqual(result.status, "success")
        self.assertIn("Tomorrow in Singapore, Singapore", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_relative_weather_answer_path_uses_default_location(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([weather_geocoding_response(), weather_daily_response()])
        history = []

        answer, route, result = answer_with_tools(
            "今天这里天气怎么样",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertEqual(route.category, "weather")
        self.assertEqual(route.params["intent"], "today")
        self.assertNotIn("location", route.params)
        self.assertEqual(client.calls[0][1]["name"], "Singapore")
        self.assertEqual(result.status, "success")
        self.assertIn("Today in Singapore, Singapore", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_successful_weather_result_can_be_naturalized_without_chat_history(self):
        chat_client = FakeNaturalizingClient(naturalized_answer="明天新加坡会下雨，温度约 24 到 31 C，来源 Open-Meteo。")
        client = FakeJsonClient([weather_geocoding_response(), weather_daily_response()])
        history = [{"role": "user", "content": "old"}]

        answer, route, result = answer_with_tools(
            "明天天气怎么样",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            naturalize_tool_answers=True,
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertEqual(answer, "明天新加坡会下雨，温度约 24 到 31 C，来源 Open-Meteo。")
        self.assertEqual(route.category, "weather")
        self.assertEqual(result.status, "success")
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [{"role": "user", "content": "old"}])
        call = chat_client.naturalization_calls[0]
        self.assertEqual(call["question"], "明天天气怎么样")
        self.assertEqual(call["route"]["category"], "weather")
        self.assertEqual(call["route"]["tool_name"], "weather_provider")
        self.assertIn("open-meteo", call["summary"])
        self.assertIn("Tomorrow in Singapore, Singapore", call["raw_answer"])
        self.assertEqual(call["data"]["source"], "open-meteo")

    def test_disabled_tool_naturalization_keeps_raw_provider_answer(self):
        chat_client = FakeNaturalizingClient()
        client = FakeJsonClient([{"date": "2026-07-03", "base": "USD", "quote": "SGD", "rate": 1.34567}])
        history = []

        answer, route, result = answer_with_tools(
            "100 USD to SGD",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            naturalize_tool_answers=False,
            provider_config=ProviderConfig(default_base_currency="USD"),
            http_client=client,
        )

        self.assertEqual(route.category, "fx")
        self.assertEqual(result.status, "success")
        self.assertIn("100 USD is about 134.57 SGD", answer)
        self.assertEqual(chat_client.naturalization_calls, [])
        self.assertEqual(history, [])

    def test_recoverable_naturalization_error_falls_back_to_raw_answer(self):
        chat_client = FakeNaturalizingClient(fail=True)
        client = FakeJsonClient([stock_quote_response()])
        history = []

        answer, route, result = answer_with_tools(
            "AAPL stock price",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            naturalize_tool_answers=True,
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
            http_client=client,
        )

        self.assertEqual(route.category, "stock")
        self.assertEqual(result.status, "success")
        self.assertIn("AAPL last traded at 193.12", answer)
        self.assertEqual(len(chat_client.naturalization_calls), 1)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_empty_naturalization_output_falls_back_to_raw_answer(self):
        chat_client = FakeNaturalizingClient(naturalized_answer="  ")
        client = FakeJsonClient([{"date": "2026-07-03", "base": "USD", "quote": "SGD", "rate": 1.34567}])

        answer, route, result = answer_with_tools(
            "100 USD to SGD",
            chat_client=chat_client,
            history=[],
            tools_enabled=True,
            naturalize_tool_answers=True,
            provider_config=ProviderConfig(default_base_currency="USD"),
            http_client=client,
        )

        self.assertEqual(route.category, "fx")
        self.assertEqual(result.status, "success")
        self.assertIn("100 USD is about 134.57 SGD", answer)

    def test_local_and_refused_tool_results_are_not_naturalized(self):
        chat_client = FakeNaturalizingClient()
        history = []

        calculator_answer, calculator_route, calculator_result = answer_with_tools(
            "2 + 2",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            naturalize_tool_answers=True,
        )
        refusal_answer, refusal_route, refusal_result = answer_with_tools(
            "今天有什么新闻",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            naturalize_tool_answers=True,
        )

        self.assertEqual(calculator_route.category, "calculator")
        self.assertEqual(calculator_result.status, "success")
        self.assertEqual(calculator_answer, "The answer is 4.")
        self.assertEqual(refusal_route.category, "unsupported_realtime")
        self.assertEqual(refusal_result.status, "refused")
        self.assertIn("without a configured provider", refusal_answer)
        self.assertEqual(chat_client.naturalization_calls, [])
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_traditional_chinese_local_tools_do_not_call_chat(self):
        chat_client = FakeChatClient()
        history = []

        time_answer, time_route, time_result = answer_with_tools(
            "現在幾點了",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            now_provider=self.local_clock,
        )
        calculator_answer, calculator_route, calculator_result = answer_with_tools(
            "100減20是多少",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
        )

        self.assertEqual(time_route.category, "time")
        self.assertEqual(time_result.status, "success")
        self.assertIn("09:08", time_answer)
        self.assertEqual(calculator_route.category, "calculator")
        self.assertEqual(calculator_result.status, "success")
        self.assertEqual(calculator_answer, "The answer is 80.")
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_weather_provider_failure_does_not_fall_back_to_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([{"results": []}])
        history = []

        answer, route, result = answer_with_tools(
            "weather in Atlantis",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(),
            http_client=client,
        )

        self.assertEqual(route.category, "weather")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.data["query"], "weather in Atlantis")
        self.assertEqual(result.data["intent"], "current")
        self.assertEqual(result.data["attempted_location"], "atlantis")
        self.assertIn("could not get weather data", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_fx_answer_path_uses_provider_and_skips_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([{"date": "2026-07-03", "base": "USD", "quote": "SGD", "rate": 1.34567}])
        history = []

        answer, route, result = answer_with_tools(
            "100 USD to SGD",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(default_base_currency="USD"),
            http_client=client,
        )

        self.assertEqual(route.category, "fx")
        self.assertEqual(result.status, "success")
        self.assertIn("100 USD is about 134.57 SGD", answer)
        self.assertIn("reference rate", answer)
        self.assertIn("Not a bank cash or trade quote", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_fx_provider_failure_does_not_fall_back_to_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([{"date": "2026-07-03", "base": "USD", "quote": "SGD"}])
        history = []

        answer, route, result = answer_with_tools(
            "USD to SGD exchange rate",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(default_base_currency="USD"),
            http_client=client,
        )

        self.assertEqual(route.category, "fx")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "foreign exchange provider error: missing_rate_fields")
        self.assertIn("could not get foreign exchange data", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_stock_answer_path_uses_provider_and_skips_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([stock_quote_response()])
        history = []

        answer, route, result = answer_with_tools(
            "AAPL stock price",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
            http_client=client,
        )

        self.assertEqual(route.category, "stock")
        self.assertEqual(route.params["symbol"], "AAPL")
        self.assertEqual(result.status, "success")
        self.assertIn("AAPL last traded at 193.12", answer)
        self.assertIn("market data may be delayed", answer)
        self.assertIn("not trading advice", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_stock_provider_failure_does_not_fall_back_to_chat(self):
        chat_client = FakeChatClient()
        client = FakeJsonClient([{"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0}])
        history = []

        answer, route, result = answer_with_tools(
            "AAPL stock price",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
            http_client=client,
        )

        self.assertEqual(route.category, "stock")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "stock market provider error: unknown_symbol")
        self.assertIn("could not get stock market data", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_stock_provider_route_reports_missing_finnhub_key(self):
        route = route_text("AAPL stock price")
        result = execute_route(route, provider_config=ProviderConfig(finnhub_api_key=None))

        self.assertEqual(route.category, "stock")
        self.assertEqual(route.params["symbol"], "AAPL")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "stock market provider error: missing_credentials")
        self.assertIn("FINNHUB_API_KEY is missing", result.answer)
        self.assertNotIn("sk-", result.answer)

    def test_ambiguous_stock_like_phrase_does_not_route_to_stock(self):
        route = route_text("苹果怎么样")

        self.assertEqual(route.category, "none")
        self.assertTrue(is_realtime_sensitive("今天苹果怎么样"))

    def test_refuses_unsupported_realtime_without_chat_fallback(self):
        chat_client = FakeChatClient()
        history = []

        answer, route, result = answer_with_tools(
            "今天有什么新闻",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
        )

        self.assertEqual(route.category, "unsupported_realtime")
        self.assertEqual(result.status, "refused")
        self.assertIn("without a configured provider", answer)
        self.assertEqual(chat_client.calls, [])
        self.assertEqual(history, [])

    def test_stable_historical_comparison_remains_on_general_chat_route(self):
        questions = (
            "中国古代人的语言交流跟现在中国哪个省份的方言类似？",
            "古代汉语和当前方言有什么区别？",
            "How is ancient Chinese different from current Chinese dialects?",
        )

        for question in questions:
            with self.subTest(question=question):
                route = route_text(question)
                self.assertEqual(route.category, "none")
                self.assertEqual(route.tool_name, "chat")
                self.assertFalse(is_realtime_sensitive(question))

    def test_historical_wording_does_not_hide_fresh_data_topics(self):
        for question in (
            "古代黄金跟现在价格有什么区别？",
            "historical Apple stock compared with the current price",
            "过去的天气和今天有什么差异？",
        ):
            with self.subTest(question=question):
                self.assertTrue(is_realtime_sensitive(question))

    def test_latest_supported_provider_question_uses_planned_tool_not_refusal(self):
        route = route_text("latest AAPL stock price")
        result = execute_route(route)

        self.assertEqual(route.category, "stock")
        self.assertEqual(route.params["symbol"], "AAPL")
        self.assertEqual(result.status, "error")
        self.assertEqual(result.summary, "stock market provider error: missing_credentials")

    def test_none_route_uses_chat_when_tools_enabled(self):
        chat_client = FakeChatClient()
        history = []

        answer, route, result = answer_with_tools(
            "tell me a short joke",
            chat_client=chat_client,
            history=history,
            tools_enabled=True,
        )

        self.assertEqual(route.category, "none")
        self.assertIsNone(result)
        self.assertEqual(answer, "chat answer")
        self.assertEqual(chat_client.calls, ["tell me a short joke"])

    def test_tools_disabled_uses_chat_even_when_route_matches(self):
        chat_client = FakeChatClient()
        history = []

        answer, route, result = answer_with_tools(
            "2 + 2",
            chat_client=chat_client,
            history=history,
            tools_enabled=False,
        )

        self.assertEqual(route.category, "calculator")
        self.assertIsNone(result)
        self.assertEqual(answer, "chat answer")
        self.assertEqual(chat_client.calls, ["2 + 2"])

    def test_text_debug_prints_route_result_and_final_answer(self):
        debug = format_text_debug(
            "现在几点",
            now_provider=self.local_clock,
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
        )

        self.assertIn("input=现在几点", debug)
        self.assertIn("route=time", debug)
        self.assertIn("tool=local_time", debug)
        self.assertIn("provider_config=", debug)
        self.assertIn("finnhub_api_key:configured", debug)
        self.assertNotIn("fh-secret", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("raw_answer=The local time is 09:08", debug)
        self.assertIn("naturalization_status=not_applicable", debug)
        self.assertIn("final_answer=The local time is 09:08", debug)

    def test_text_debug_prints_traditional_chinese_local_tools(self):
        time_debug = format_text_debug("現在幾點了", now_provider=self.local_clock)
        calculator_debug = format_text_debug("100減20是多少")

        self.assertIn("route=time", time_debug)
        self.assertIn("tool=local_time", time_debug)
        self.assertIn("raw_answer=The local time is 09:08", time_debug)
        self.assertIn("route=calculator", calculator_debug)
        self.assertIn("tool=safe_calculator", calculator_debug)
        self.assertIn("raw_answer=The answer is 80.", calculator_debug)

    def test_text_debug_can_show_mocked_weather_result(self):
        client = FakeJsonClient([weather_geocoding_response(), weather_daily_response()])

        debug = format_text_debug(
            "tomorrow weather",
            provider_config=ProviderConfig(default_location="Singapore"),
            http_client=client,
        )

        self.assertIn("route=weather", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("raw_answer=Tomorrow in Singapore", debug)
        self.assertIn("naturalization_status=not_run_text_debug", debug)
        self.assertIn("Open-Meteo forecast for 2026-07-07", debug)

    def test_text_debug_can_show_mocked_fx_result(self):
        client = FakeJsonClient([{"date": "2026-07-03", "base": "EUR", "quote": "JPY", "rate": 171.2345}])

        debug = format_text_debug(
            "25 EUR to JPY",
            provider_config=ProviderConfig(default_base_currency="USD"),
            http_client=client,
        )

        self.assertIn("route=fx", debug)
        self.assertIn("params={amount:25,base:EUR,query:25 EUR to JPY,quote:JPY}", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("25 EUR is about 4280.86 JPY", debug)

    def test_text_debug_can_show_mocked_stock_result_without_secret(self):
        client = FakeJsonClient([stock_quote_response()])

        debug = format_text_debug(
            "Apple stock price",
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
            http_client=client,
        )

        self.assertIn("route=stock", debug)
        self.assertIn("params={query:Apple stock price,symbol:AAPL}", debug)
        self.assertIn("finnhub_api_key:configured", debug)
        self.assertNotIn("fh-secret", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("AAPL last traded at 193.12", debug)

    def test_text_debug_passes_resolved_watchlist_symbol_to_finnhub(self):
        client = FakeJsonClient([stock_quote_response()])

        debug = format_text_debug(
            "SpaceX 股价",
            provider_config=ProviderConfig(finnhub_api_key="fh-secret"),
            http_client=client,
        )

        self.assertIn("route=stock", debug)
        self.assertIn("symbol:SPCX", debug)
        self.assertIn("result_status=success", debug)
        self.assertIn("SPCX last traded at 193.12", debug)


if __name__ == "__main__":
    unittest.main()
