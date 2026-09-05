import queue
import threading

from lychnia.orchestrator.events import EventBus


def test_publish_reaches_every_subscriber():
    bus = EventBus()
    q1, q2 = bus.subscribe(), bus.subscribe()
    ev = bus.publish("task.started", task="plan", run=1)
    assert ev.type == "task.started" and ev.payload == {"task": "plan", "run": 1} and ev.t
    assert q1.get_nowait() is ev and q2.get_nowait() is ev
    bus.unsubscribe(q2)
    bus.publish("task.log", msg="x")
    assert q1.get_nowait().type == "task.log"
    try:
        q2.get_nowait()
        raise AssertionError("q2 still subscribed")
    except queue.Empty:
        pass


def test_publish_from_threads_is_safe():
    bus = EventBus()
    q = bus.subscribe()
    threads = [threading.Thread(target=lambda: [bus.publish("task.progress", pct=i) for i in range(100)])
               for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert q.qsize() == 400
