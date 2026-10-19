/*
 * Observer desk poll.
 *
 * The panel keeps the last good snapshot when a poll times out or fails.
 * It clears only on an explicit empty answer (status "empty"). A warming
 * payload is not an empty book. Polls do not overlap, and stop() aborts
 * the request in flight (page hide / unmount).
 *
 * This is the only /api/observers loop. The 15s desk load does not fetch
 * observers, and there is no second timer in index.html. pause() is the
 * hidden-tab guard: it clears the next-poll timer and does not start a
 * request. An in-flight request is left to the 4s abort. resume() polls
 * once. stop() is permanent (navigation away).
 *
 * Loaded as a classic script by the desk and as a CommonJS module by tests.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  if (root) root.ObserverPoll = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  var SUCCESS_MS = 15000;
  var FAILURE_BASE_MS = 2000;
  var MAX_BACKOFF_MS = 60000;
  var JITTER_RATIO = 0.2;
  var DEFAULT_TIMEOUT_MS = 4000;

  function isExplicitEmpty(payload) {
    return !!(
      payload &&
      payload.empty === true &&
      payload.status === "empty" &&
      payload.warming !== true
    );
  }

  function isWarming(payload) {
    return !!(payload && (payload.warming === true || payload.status === "warming"));
  }

  function isReady(payload) {
    return !!(
      payload &&
      payload.status === "ready" &&
      payload.warming !== true &&
      payload.empty !== true &&
      Array.isArray(payload.observers) &&
      payload.observers.length > 0
    );
  }

  function hasCards(payload) {
    return !!(payload && Array.isArray(payload.observers) && payload.observers.length > 0 && !isWarming(payload));
  }

  // What the panel should draw from the current view. "cards" is the last
  // good snapshot. "empty" is the server's explicit empty answer. Anything
  // else stays on the warming message so a timeout cannot look like no data.
  function panelMode(view) {
    var data = view && view.data;
    if (isExplicitEmpty(data)) return "empty";
    if (hasCards(data)) return "cards";
    return "warming";
  }

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  // "updated Xs ago" while the last poll succeeded. "stale since HH:MM"
  // (UTC, from generated_at) when that poll failed.
  function freshnessLabel(payload, pollFailed, nowMs) {
    if (!payload || !payload.generated_at) return "";
    var then = Date.parse(payload.generated_at);
    if (!Number.isFinite(then)) return "";
    if (pollFailed) {
      var stamp = new Date(then);
      return "stale since " + pad2(stamp.getUTCHours()) + ":" + pad2(stamp.getUTCMinutes());
    }
    var seconds = Math.max(0, Math.floor((Number(nowMs) - then) / 1000));
    return "updated " + seconds + "s ago";
  }

  function applyJitter(ms, random) {
    var roll = random();
    var delta = ms * JITTER_RATIO;
    return Math.max(0, Math.round(ms + (roll * 2 - 1) * delta));
  }

  // Success waits the base interval. Failures double from 2s up to 60s.
  // `random` in [0, 1) spreads that delay by ±20%.
  function nextDelayMs(outcome, failures, random) {
    var roll = typeof random === "function" ? random : Math.random;
    var base;
    if (outcome === "failure" || outcome === "timeout") {
      var n = Math.max(1, failures || 1);
      base = Math.min(MAX_BACKOFF_MS, FAILURE_BASE_MS * Math.pow(2, n - 1));
    } else {
      base = SUCCESS_MS;
    }
    return applyJitter(base, roll);
  }

  function anySignal(signals) {
    var controller = new AbortController();
    function onAbort(signal) {
      if (!controller.signal.aborted) controller.abort(signal.reason);
    }
    for (var i = 0; i < signals.length; i++) {
      var signal = signals[i];
      if (!signal) continue;
      if (signal.aborted) {
        onAbort(signal);
        break;
      }
      signal.addEventListener("abort", onAbort.bind(null, signal), { once: true });
    }
    return controller.signal;
  }

  function reduce(view, event) {
    var current = view || { data: null, failed: false, error: null };
    var type = event && event.type;
    if (type === "success") {
      var payload = event.payload;
      if (isExplicitEmpty(payload)) {
        return { data: payload, failed: false, error: null };
      }
      if (isWarming(payload)) {
        if (hasCards(current.data)) {
          return { data: current.data, failed: false, error: null };
        }
        return { data: payload, failed: false, error: null };
      }
      if (isReady(payload)) {
        return { data: payload, failed: false, error: null };
      }
      // A 200 that is not ready, warming, or explicit-empty must not wipe
      // the cards. The old client treated `{observers: []}` as that wipe.
      return {
        data: current.data,
        failed: true,
        error: (event && event.error) || "unusable payload",
      };
    }
    if (type === "failure" || type === "timeout") {
      return {
        data: current.data,
        failed: true,
        error: (event && event.error) || type,
      };
    }
    return current;
  }

  function unref(timer) {
    if (timer && typeof timer.unref === "function") timer.unref();
  }

  function create(options) {
    var opts = options || {};
    var fetchPayload = opts.fetchPayload;
    var onChange = typeof opts.onChange === "function" ? opts.onChange : function () {};
    var timeoutMs = opts.timeoutMs || DEFAULT_TIMEOUT_MS;
    var random = opts.random || Math.random;
    var view = { data: null, failed: false, error: null };
    var inFlight = false;
    var stopped = false;
    var paused = false;
    var failures = 0;
    var controller = null;
    var retryTimer = null;
    var lastDelay = null;

    function schedule(outcome) {
      if (stopped || paused) return;
      if (retryTimer) clearTimeout(retryTimer);
      lastDelay = nextDelayMs(outcome, failures, random);
      retryTimer = setTimeout(function () {
        retryTimer = null;
        poll();
      }, lastDelay);
      unref(retryTimer);
    }

    function poll() {
      if (stopped || paused || inFlight) return Promise.resolve(view);
      inFlight = true;
      var local = new AbortController();
      controller = local;
      var timedOut = false;
      var timeoutTimer = setTimeout(function () {
        timedOut = true;
        local.abort();
      }, timeoutMs);
      unref(timeoutTimer);
      // Start the request before poll() returns so a second call sees
      // inFlight and stop() aborts a request that has already begun.
      var pending;
      try {
        pending = fetchPayload(local.signal);
      } catch (err) {
        pending = Promise.reject(err);
      }
      return Promise.resolve(pending)
        .then(function (payload) {
          if (stopped) return view;
          failures = 0;
          view = reduce(view, { type: "success", payload: payload });
          onChange(view);
          schedule("success");
          return view;
        })
        .catch(function (err) {
          if (stopped) return view;
          failures += 1;
          var isTimeout = timedOut || (err && err.name === "TimeoutError");
          view = reduce(view, {
            type: isTimeout ? "timeout" : "failure",
            error: String((err && err.message) || err || (isTimeout ? "timeout" : "failure")),
          });
          onChange(view);
          schedule(isTimeout ? "timeout" : "failure");
          return view;
        })
        .finally(function () {
          clearTimeout(timeoutTimer);
          if (controller === local) controller = null;
          inFlight = false;
        });
    }

    function stop() {
      stopped = true;
      paused = false;
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = null;
      if (controller) controller.abort();
    }

    // Hidden tab: drop the scheduled poll. Do not abort the request already
    // in flight; the timeout still caps it. Cards stay as they are.
    function pause() {
      if (stopped) return;
      paused = true;
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = null;
    }

    // Visible again: one poll, then the normal interval. Not a second loop.
    function resume() {
      if (stopped) return Promise.resolve(view);
      var wasPaused = paused;
      paused = false;
      if (!wasPaused || inFlight) return Promise.resolve(view);
      return poll();
    }

    return {
      start: function () {
        if (stopped) return Promise.resolve(view);
        return poll();
      },
      stop: stop,
      pause: pause,
      resume: resume,
      poll: poll,
      getView: function () {
        return view;
      },
      inFlight: function () {
        return inFlight;
      },
      paused: function () {
        return paused;
      },
      lastDelay: function () {
        return lastDelay;
      },
    };
  }

  return {
    SUCCESS_MS: SUCCESS_MS,
    FAILURE_BASE_MS: FAILURE_BASE_MS,
    MAX_BACKOFF_MS: MAX_BACKOFF_MS,
    DEFAULT_TIMEOUT_MS: DEFAULT_TIMEOUT_MS,
    create: create,
    reduce: reduce,
    panelMode: panelMode,
    freshnessLabel: freshnessLabel,
    nextDelayMs: nextDelayMs,
    anySignal: anySignal,
    isExplicitEmpty: isExplicitEmpty,
    isWarming: isWarming,
  };
});
