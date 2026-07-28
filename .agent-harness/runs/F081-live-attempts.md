# F081 Live Realtime Weather Attempts

## Scope

These were user-authorized, billable Realtime sessions on the target Mac using
its built-in microphone and speaker. Evidence is content-redacted except for
the user-supplied acceptance phrases and bounded location/result labels needed
to distinguish Singapore from Japan's Tokyo.

## Initial Results

- The user reported that default Singapore weather worked only after several
  attempts.
- Sanitized lifecycle evidence showed the first three connected sessions
  received no `speech_started` event before idle-timeout cleanup. They did not
  invoke the weather tool, so those failures are classified as missing live
  input rather than intermittent provider execution.
- A later session captured speech, executed one de-duplicated weather call,
  returned one correlated result, played the answer, and recovered wake
  ownership.
- An explicit `东京` request also reached and completed the Realtime tool
  lifecycle, but the user reported that Tokyo was not successfully returned.

## Reproduction and Correction

The same explicit request was reproduced outside Realtime through the existing
text-tool path:

```text
明天东京天气怎么样
```

Before correction it returned structured provider error
`no_location_match`. The geocoding provider's Chinese-language search was not
used as a global fix because a direct probe resolved `东京` to same-name
locations in China rather than Tokyo, Japan.

The provider boundary now normalizes unambiguous Chinese references
`东京`/`東京` and their Japan/city variants to the provider query `Tokyo`.
Focused tests assert that the original Chinese request produces the query
`Tokyo` and returns `Tokyo, Japan`. A real text-tool provider query after the
correction successfully returned the next-day Tokyo, Japan forecast.

## Post-correction Realtime Result

A fresh Realtime session after correction recorded:

- input speech start and stop;
- exactly one weather execution, with duplicate event suppression;
- one correlated tool result followed by a new model response;
- answer playback;
- semantic end-phrase handling; and
- cleanup to `wake_owned` with the wake microphone reopened.

This proves the corrected request completed the live Realtime tool and cleanup
path. The user then confirmed that the audible answer was Chinese weather for
Tokyo, Japan. Together with the earlier successful default-Singapore answer,
the explicit-location and cleanup portions of M081 pass. Separate cold-start
evaluator approval remains pending, and no evaluator pass is claimed here.
