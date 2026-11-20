"""7.2.8、7.6；OBJ-029、FLD-EVT-021；迟到事实追加。"""
from conformance.checks import Checks


def run(ctx):
    c = Checks(ctx, "T06")
    sent = []
    for i, offset in enumerate((-10, -20, -30)):
        event = c.event(str(i))
        event.update(occurred_at=ctx.time(offset), source_sequence=i + 1)
        sent.append(event)
        c.status("send" + str(i), c.call("accept_event", event=event), "accepted")
    occurred = c.events()
    received = c.call("query_events", instance=c.app["object_id"], order_by="received_at")["events"]
    c.observe("orders", [e["source_sequence"] for e in occurred] == [3, 2, 1] and [e["source_sequence"] for e in received] == [1, 2, 3],
              {"occurred_order": [e["source_sequence"] for e in occurred], "received_order": [e["source_sequence"] for e in received]})
    preserved = len(received) == 3 and all(all(row.get(k) == v for k, v in original.items()) and row["received_at"] > row["occurred_at"] for row, original in zip(received, sent))
    c.observe("append", preserved, "迟到追加三条，原 occurred_at/载荷保持=" + str(preserved))
    c.status("bad-order", c.call("query_events", instance=c.app["object_id"], order_by="unregistered"), "rejected")
    return c.results
