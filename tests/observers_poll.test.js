"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const poll = require("../api/static/observers_poll.js");

const READY = {
  status: "ready",
  warming: false,
  empty: false,
  generated_at: "2026-10-19T21:08:30.000000Z",
  observers: [
    { id: "f111", label: "F111" },
    { id: "bl8", label: "BL8" },
  ],
  pulses: [{ id: "f111" }, { id: "bl8" }],
};

const EMPTY = {
  status: "empty",
  warming: false,
  empty: true,
  generated_at: "2026-10-19T21:12:00.000000Z",
  observers: [],
  pulses: [],
};

function withCards() {
  return poll.reduce(
    { data: null, failed: false, error: null },
    { type: "success", payload: READY },
  );
}

test("failed or timed-out poll keeps the previous render", () => {
  const shown = withCards();
  assert.equal(poll.panelMode(shown), "cards");
  assert.equal(shown.data.observers[0].label, "F111");

  const timedOut = poll.reduce(shown, { type: "timeout", error: "TimeoutError" });
  assert.equal(poll.panelMode(timedOut), "cards");
  assert.equal(timedOut.failed, true);
  assert.equal(timedOut.data.observers[0].id, "f111");
  assert.equal(timedOut.data.observers[1].id, "bl8");
  assert.equal(
    poll.freshnessLabel(timedOut.data, true, Date.parse("2026-10-19T21:10:00Z")),
    "stale since 21:08",
  );

  const failed = poll.reduce(timedOut, { type: "failure", error: "/api/observers 500" });
  assert.equal(poll.panelMode(failed), "cards");
  assert.equal(failed.data, timedOut.data);
  assert.equal(failed.data.observers[0].label, "F111");
  assert.equal(
    poll.freshnessLabel(failed.data, false, Date.parse("2026-10-19T21:08:35Z")),
    "updated 5s ago",
  );

  // The old client synthesised this on catch and the panel went blank.
  const bogusEmpty = poll.reduce(failed, {
    type: "success",
    payload: { ok: false, error: "timeout", observers: [], pulses: [] },
  });
  assert.equal(poll.panelMode(bogusEmpty), "cards");
  assert.equal(bogusEmpty.data.observers[0].id, "f111");
  assert.equal(bogusEmpty.failed, true);
});

test("explicit empty state clears the previous render", () => {
  const shown = withCards();
  const cleared = poll.reduce(shown, { type: "success", payload: EMPTY });
  assert.equal(poll.panelMode(cleared), "empty");
  assert.equal(cleared.failed, false);
  assert.deepEqual(cleared.data.observers, []);
  assert.equal(cleared.data.observers.length, 0);
  assert.ok(!cleared.data.observers.some((row) => row.id === "f111"));
  assert.equal(
    poll.freshnessLabel(cleared.data, false, Date.parse("2026-10-19T21:12:04Z")),
    "updated 4s ago",
  );
});

test("warming is not an empty book and does not drop cards", () => {
  const warming = {
    status: "warming",
    warming: true,
    empty: false,
    generated_at: null,
    observers: null,
    pulses: null,
  };
  const first = poll.reduce(
    { data: null, failed: false, error: null },
    { type: "success", payload: warming },
  );
  assert.equal(poll.panelMode(first), "warming");
  assert.equal(first.data.observers, null);

  const kept = poll.reduce(withCards(), { type: "success", payload: warming });
  assert.equal(poll.panelMode(kept), "cards");
  assert.equal(kept.data.observers[0].id, "f111");
});

test("failures back off and a success returns to the base interval", async () => {
  let calls = 0;
  const client = poll.create({
    random: () => 0.5,
    timeoutMs: 1000,
    fetchPayload: async () => {
      calls += 1;
      if (calls < 3) throw new Error("tunnel stalled");
      return READY;
    },
  });
  try {
    await client.poll();
    assert.equal(client.lastDelay(), poll.FAILURE_BASE_MS);
    assert.equal(poll.panelMode(client.getView()), "warming");
    await client.poll();
    assert.equal(client.lastDelay(), poll.FAILURE_BASE_MS * 2);
    await client.poll();
    assert.equal(client.lastDelay(), poll.SUCCESS_MS);
    assert.equal(poll.panelMode(client.getView()), "cards");
    assert.equal(client.getView().failed, false);
  } finally {
    client.stop();
  }
});

test("jitter spreads the delay by twenty percent", () => {
  assert.equal(poll.nextDelayMs("success", 0, () => 0.5), poll.SUCCESS_MS);
  assert.equal(poll.nextDelayMs("success", 0, () => 0), Math.round(poll.SUCCESS_MS * 0.8));
  assert.equal(poll.nextDelayMs("success", 0, () => 1), Math.round(poll.SUCCESS_MS * 1.2));
  const capped = poll.nextDelayMs("failure", 12, () => 0.5);
  assert.equal(capped, poll.MAX_BACKOFF_MS);
});

test("polls do not overlap", async () => {
  let active = 0;
  let maxActive = 0;
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const client = poll.create({
    timeoutMs: 5000,
    fetchPayload: (signal) => {
      active += 1;
      maxActive = Math.max(maxActive, active);
      return new Promise((resolve, reject) => {
        const finish = () => {
          active -= 1;
          resolve(READY);
        };
        const abort = () => {
          active -= 1;
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        };
        if (signal.aborted) {
          abort();
          return;
        }
        signal.addEventListener("abort", abort, { once: true });
        gate.then(() => {
          signal.removeEventListener("abort", abort);
          finish();
        });
      });
    },
  });
  try {
    const first = client.poll();
    const second = client.poll();
    assert.equal(maxActive, 1);
    assert.equal(client.inFlight(), true);
    await second;
    release();
    await first;
    assert.equal(maxActive, 1);
    assert.equal(poll.panelMode(client.getView()), "cards");
  } finally {
    client.stop();
  }
});

test("stop aborts the in-flight request and does not clear cards", async () => {
  const shown = poll.create({
    timeoutMs: 5000,
    fetchPayload: async () => READY,
  });
  try {
    await shown.poll();
  } finally {
    shown.stop();
  }
  assert.equal(poll.panelMode(shown.getView()), "cards");

  let sawAbort = false;
  const client = poll.create({
    timeoutMs: 5000,
    fetchPayload: (signal) =>
      new Promise((resolve, reject) => {
        const fail = () => {
          sawAbort = true;
          const err = new Error("aborted");
          err.name = "AbortError";
          reject(err);
        };
        if (signal.aborted) {
          fail();
          return;
        }
        signal.addEventListener("abort", fail, { once: true });
      }),
  });
  const pending = client.poll();
  client.stop();
  await pending;
  assert.equal(sawAbort, true);
  assert.equal(client.getView().failed, false);
  assert.equal(client.getView().data, null);
});
