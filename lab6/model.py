"""Visitor demand, itineraries, and the finite-capacity mall simulation."""

import heapq
import math
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from itertools import count
from random import Random


HOURLY_RATES = (35, 60, 90, 105, 75, 45)
AREAS = ("parking", "retail", "shop_a", "shop_b", "order", "tables", "gate")
# Triangular duration parameters in minutes, in (minimum, mode, maximum) order.
SERVICE = {
    "retail": (15, 25, 45),
    "shop_a": (10, 18, 32),
    "shop_b": (10, 18, 32),
    "order": (2, 4, 7),
    "gate": (0.4, 0.8, 1.8),
}


@dataclass(frozen=True)
class Capacities:
    parking: int = 72
    outside: int = 12
    retail: int = 20
    shop_a: int = 12
    shop_b: int = 12
    order: int = 4
    tables: int = 12
    gate: int = 2

    def __post_init__(self):
        for area in (*AREAS, "outside"):
            capacity = getattr(self, area)
            minimum = 0 if area == "outside" else 1
            if not isinstance(capacity, int) or capacity < minimum:
                raise ValueError(f"{area} capacity must be an integer of at least {minimum}")


@dataclass(frozen=True)
class Stop:
    area: str
    walk: float
    service: float

    def __post_init__(self):
        if self.area not in SERVICE:
            raise ValueError(f"unknown service area {self.area}")
        if not all(math.isfinite(t) and t >= 0 for t in (self.walk, self.service)):
            raise ValueError("walking and service durations must be finite and nonnegative")


@dataclass(frozen=True)
class Visit:
    arrival: float
    stops: tuple[Stop, ...]
    meal: float = 0.0

    def __post_init__(self):
        if not all(math.isfinite(t) and t >= 0 for t in (self.arrival, self.meal)):
            raise ValueError("arrival time and meal duration must be finite and nonnegative")
        if not self.stops or self.stops[-1].area != "gate" or any(s.area == "gate" for s in self.stops[:-1]):
            raise ValueError("every itinerary must end in a single payment gate visit")


def _triangular(rng: Random, low: float, mode: float, high: float) -> float:
    return rng.triangular(low, high, mode)


def _itinerary(arrival: float, rng: Random) -> Visit:
    profile = rng.random()
    if profile < 0.40:
        route = ["retail"]
        dine = rng.random() < 0.20
    elif profile < 0.75:
        shops = ["shop_a", "shop_b"]
        rng.shuffle(shops)
        route = shops if rng.random() < 0.65 else shops[:1]
        dine = rng.random() < (0.50 if len(route) == 2 else 0.20)
    else:
        route = []
        dine = True

    meal = 0.0
    if dine:
        route.append("order")
        meal = _triangular(rng, 14, 24, 37)
    route.append("gate")
    stops = tuple(Stop(area, _triangular(rng, 1, 2, 5), _triangular(rng, *SERVICE[area])) for area in route)
    return Visit(arrival, stops, meal)


def generate_day(rng: Random, hourly_rates: Sequence[float] = HOURLY_RATES) -> list[Visit]:
    """Draw a piecewise-constant Poisson arrival stream and a complete plan per arrival."""
    arrivals = []
    for hour, rate in enumerate(hourly_rates):
        if not math.isfinite(rate) or rate < 0:
            raise ValueError("hourly rates must be finite and nonnegative")
        if rate == 0:
            continue
        time = 60 * hour + rng.expovariate(rate / 60)
        while time < 60 * (hour + 1):
            arrivals.append(time)
            time += rng.expovariate(rate / 60)
    return [_itinerary(arrival, rng) for arrival in arrivals]


@dataclass
class _Visitor:
    plan: Visit
    step: int = 0
    waiting_since: float = 0.0

    @property
    def stop(self) -> Stop:
        return self.plan.stops[self.step]


@dataclass
class _Resource:
    capacity: int
    busy: int = 0
    queue: deque[_Visitor] = field(default_factory=deque)
    busy_minutes: float = 0.0
    full_minutes: float = 0.0


Metrics = dict[str, float | None]
Event = Callable[[_Visitor], None]


class _Mall:
    def __init__(self, capacities: Capacities, horizon: float):
        self.horizon = horizon
        self.outside_limit = capacities.outside
        self.areas = {name: _Resource(getattr(capacities, name)) for name in AREAS}
        self.now = 0.0
        self.serial = count()
        self.calendar: list[tuple[float, bool, int, Event, _Visitor]] = []
        self.arrivals = self.lost = self.departures = 0
        self.orders = self.blocked_orders = self.full_on_arrival = 0
        self.sojourn = self.outside_wait = self.order_wait = self.table_wait = 0.0
        self.blocked_counter_minutes = 0.0

    def schedule(self, time: float, event: Event, visitor: _Visitor, *, arrival: bool = False):
        # Internal transfers and departures take priority over simultaneous new arrivals.
        heapq.heappush(self.calendar, (time, arrival, next(self.serial), event, visitor))

    def advance(self, time: float):
        dt = min(time, self.horizon) - min(self.now, self.horizon)
        for resource in self.areas.values():
            if not 0 <= resource.busy <= resource.capacity:
                raise RuntimeError("resource occupancy outside capacity bounds")
            resource.busy_minutes += dt * resource.busy
            if resource.busy == resource.capacity:
                resource.full_minutes += dt
        blocked = len(self.areas["tables"].queue)
        if blocked > self.areas["order"].busy:
            raise RuntimeError("each visitor waiting for a table must still hold a counter")
        self.blocked_counter_minutes += dt * blocked
        self.now = time

    def arrive(self, visitor: _Visitor):
        self.arrivals += 1
        lot = self.areas["parking"]
        if lot.busy < lot.capacity:
            self.park(visitor)
        else:
            self.full_on_arrival += 1
            if len(lot.queue) < self.outside_limit:
                lot.queue.append(visitor)
            else:
                self.lost += 1

    def park(self, visitor: _Visitor):
        self.areas["parking"].busy += 1
        self.outside_wait += self.now - visitor.plan.arrival
        self.walk(visitor)

    def walk(self, visitor: _Visitor):
        self.schedule(self.now + visitor.stop.walk, self.join_service, visitor)

    def join_service(self, visitor: _Visitor):
        resource = self.areas[visitor.stop.area]
        visitor.waiting_since = self.now
        if resource.busy < resource.capacity:
            self.start_service(visitor)
        else:
            resource.queue.append(visitor)

    def start_service(self, visitor: _Visitor):
        area = visitor.stop.area
        self.areas[area].busy += 1
        if area == "order":
            self.orders += 1
            self.order_wait += self.now - visitor.waiting_since
        self.schedule(self.now + visitor.stop.service, self.finish_service, visitor)

    def release_server(self, area: str):
        resource = self.areas[area]
        resource.busy -= 1
        if resource.queue:
            self.start_service(resource.queue.popleft())

    def finish_service(self, visitor: _Visitor):
        area = visitor.stop.area
        if area == "order":
            tables = self.areas["tables"]
            visitor.waiting_since = self.now
            if tables.busy == tables.capacity:
                self.blocked_orders += 1
                tables.queue.append(visitor)  # still occupying the same ordering counter
            else:
                self.seat(visitor)
            return

        self.release_server(area)
        if area == "gate":
            self.departures += 1
            self.sojourn += self.now - visitor.plan.arrival
            lot = self.areas["parking"]
            lot.busy -= 1
            if lot.queue:
                self.park(lot.queue.popleft())
        else:
            self.next_stop(visitor)

    def seat(self, visitor: _Visitor):
        self.areas["tables"].busy += 1
        self.table_wait += self.now - visitor.waiting_since
        self.release_server("order")
        self.schedule(self.now + visitor.plan.meal, self.finish_meal, visitor)

    def finish_meal(self, visitor: _Visitor):
        tables = self.areas["tables"]
        tables.busy -= 1
        if tables.queue:
            self.seat(tables.queue.popleft())
        self.next_stop(visitor)

    def next_stop(self, visitor: _Visitor):
        visitor.step += 1
        self.walk(visitor)

    def run(self, visits: Iterable[Visit]) -> Metrics:
        for plan in visits:
            if not 0 <= plan.arrival < self.horizon:
                raise ValueError("arrivals must be within the half-open observation window")
            self.schedule(plan.arrival, self.arrive, _Visitor(plan), arrival=True)
        while self.calendar:
            time, _, _, event, visitor = heapq.heappop(self.calendar)
            self.advance(time)
            event(visitor)
        if self.arrivals != self.departures + self.lost or any(r.busy or r.queue for r in self.areas.values()):
            raise RuntimeError("the mall did not drain or visitor counts did not balance")
        return self.metrics()

    def metrics(self) -> Metrics:
        def per(total: float, count: int) -> float | None:
            return total / count if count else None

        result = {
            "arrivals": self.arrivals,
            "departures": self.departures,
            "loss_pct": per(100 * self.lost, self.arrivals),
            "sojourn_min": per(self.sojourn, self.departures),
            "outside_wait_min": per(self.outside_wait, self.departures),
            "order_wait_min": per(self.order_wait, self.orders),
            "table_wait_min": per(self.table_wait, self.orders),
            "lot_full_on_arrival_pct": per(100 * self.full_on_arrival, self.arrivals),
            "orders_blocked_pct": per(100 * self.blocked_orders, self.orders),
            "counter_blocked_pct": 100 * self.blocked_counter_minutes / (self.horizon * self.areas["order"].capacity),
        }
        for name, resource in self.areas.items():
            result[f"{name}_util_pct"] = 100 * resource.busy_minutes / (self.horizon * resource.capacity)
        for name in ("parking", "tables"):
            result[f"{name}_full_pct"] = 100 * self.areas[name].full_minutes / self.horizon
        return result


def simulate(visits: Iterable[Visit], capacities: Capacities = Capacities(), horizon: float = 360) -> Metrics:
    """Open empty at minute zero, accept arrivals before horizon, then drain every queue."""
    if not math.isfinite(horizon) or horizon <= 0:
        raise ValueError("the observation window must be finite and positive")
    return _Mall(capacities, horizon).run(visits)
