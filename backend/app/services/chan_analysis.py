from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

CHAN_ALGORITHM_CODE = "vespa314_chan_py"
CHAN_ALGORITHM_VERSION = 1
CHAN_ALGORITHM_PARAMETERS: dict[str, Any] = {
    "source": "Vespa314/chan.py",
    "source_commit": "429d6ed3043e",
    "license": "MIT",
    "engine": "vendored",
    "config": {
        "trigger_step": True,
        "kl_data_check": False,
        "bi_strict": True,
        "bi_fx_check": "strict",
        "seg_algo": "chan",
        "zs_combine": True,
        "bs_type": "1,1p,2,2s,3a,3b",
    },
    "status_policy": "chan_py_is_sure_false_maps_to_provisional",
}

ChanDirection = Literal["up", "down", "neutral"]
ChanElementStatus = Literal["confirmed", "provisional"]
ChanFractalKind = Literal["top", "bottom"]
ChanObservationSide = Literal["buy", "sell"]
ChanFrequency = Literal["daily", "30m", "60m"]


@dataclass(frozen=True, slots=True)
class ChanBar:
    index: int
    trade_date: date
    timestamp: datetime | None
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal = Decimal("0")
    amount: Decimal | None = None

    @property
    def bar_time(self) -> str:
        if self.timestamp:
            return self.timestamp.isoformat()
        return self.trade_date.isoformat()


@dataclass(frozen=True, slots=True)
class ChanFractal:
    index: int
    bar_time: str
    trade_date: date
    timestamp: datetime | None
    kind: ChanFractalKind
    price: Decimal
    status: ChanElementStatus


@dataclass(frozen=True, slots=True)
class ChanStroke:
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    direction: ChanDirection
    price_low: Decimal
    price_high: Decimal
    status: ChanElementStatus


@dataclass(frozen=True, slots=True)
class ChanSegment:
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    direction: ChanDirection
    price_low: Decimal
    price_high: Decimal
    status: ChanElementStatus
    stroke_indexes: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ChanCenter:
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    price_low: Decimal
    price_high: Decimal
    status: ChanElementStatus
    stroke_indexes: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ChanObservation:
    index: int
    bar_time: str
    trade_date: date
    timestamp: datetime | None
    kind: str
    side: ChanObservationSide
    label: str
    price: Decimal
    status: ChanElementStatus
    explanation: str


@dataclass(frozen=True, slots=True)
class ChanAnalysis:
    fractals: tuple[ChanFractal, ...]
    strokes: tuple[ChanStroke, ...]
    segments: tuple[ChanSegment, ...]
    centers: tuple[ChanCenter, ...]
    observations: tuple[ChanObservation, ...]


@dataclass(frozen=True, slots=True)
class _ChanPyModules:
    CChan: Any
    CChanConfig: Any
    CTime: Any
    CKLineUnit: Any
    DATA_FIELD: Any
    FX_TYPE: Any
    BI_DIR: Any
    KL_TYPE: Any


def decimal_value(value: Decimal | float | int | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def analyze_chan_structure(
    bars: tuple[ChanBar, ...],
    frequency: ChanFrequency = "daily",
) -> ChanAnalysis:
    if len(bars) < 3:
        return ChanAnalysis(
            fractals=(),
            strokes=(),
            segments=(),
            centers=(),
            observations=(),
        )

    modules = _load_chan_py_modules()
    chan = _run_chan_py(bars, frequency, modules)
    kline_list = chan[0]
    return ChanAnalysis(
        fractals=tuple(_extract_fractals(kline_list, bars, modules)),
        strokes=tuple(_extract_strokes(kline_list, bars)),
        segments=tuple(_extract_segments(kline_list, bars, modules)),
        centers=tuple(_extract_centers(kline_list, bars)),
        observations=tuple(_extract_observations(kline_list, bars)),
    )


def _load_chan_py_modules() -> _ChanPyModules:
    vendor_root = Path(__file__).resolve().parents[3] / "third_party" / "chan_py"
    if str(vendor_root) not in sys.path:
        sys.path.insert(0, str(vendor_root))

    chan_module = import_module("Chan")
    config_module = import_module("ChanConfig")
    enum_module = import_module("Common.CEnum")
    time_module = import_module("Common.CTime")
    kline_unit_module = import_module("KLine.KLine_Unit")
    return _ChanPyModules(
        CChan=chan_module.CChan,
        CChanConfig=config_module.CChanConfig,
        CTime=time_module.CTime,
        CKLineUnit=kline_unit_module.CKLine_Unit,
        DATA_FIELD=enum_module.DATA_FIELD,
        FX_TYPE=enum_module.FX_TYPE,
        BI_DIR=enum_module.BI_DIR,
        KL_TYPE=enum_module.KL_TYPE,
    )


def _run_chan_py(
    bars: tuple[ChanBar, ...],
    frequency: ChanFrequency,
    modules: _ChanPyModules,
) -> Any:
    config = modules.CChanConfig(
        {
            "trigger_step": True,
            "kl_data_check": False,
            "print_warning": False,
            "print_err_time": False,
            "bi_strict": True,
            "bi_fx_check": "strict",
            "seg_algo": "chan",
            "zs_combine": True,
            "bs_type": "1,1p,2,2s,3a,3b",
        }
    )
    kl_type = _kl_type_for_frequency(frequency, modules)
    chan = modules.CChan(
        "LOCAL",
        data_src="custom:unused.Unused",
        lv_list=[kl_type],
        config=config,
    )
    chan.trigger_load({kl_type: [_kline_unit_from_bar(bar, modules) for bar in bars]})
    return chan


def _kl_type_for_frequency(frequency: ChanFrequency, modules: _ChanPyModules) -> Any:
    if frequency == "30m":
        return modules.KL_TYPE.K_30M
    if frequency == "60m":
        return modules.KL_TYPE.K_60M
    return modules.KL_TYPE.K_DAY


def _kline_unit_from_bar(bar: ChanBar, modules: _ChanPyModules) -> Any:
    fields = modules.DATA_FIELD
    data: dict[str, Any] = {
        fields.FIELD_TIME: _ctime_from_bar(bar, modules),
        fields.FIELD_OPEN: float(bar.open),
        fields.FIELD_HIGH: float(bar.high),
        fields.FIELD_LOW: float(bar.low),
        fields.FIELD_CLOSE: float(bar.close),
        fields.FIELD_VOLUME: float(bar.volume),
    }
    if bar.amount is not None:
        data[fields.FIELD_TURNOVER] = float(bar.amount)
    return modules.CKLineUnit(data)


def _ctime_from_bar(bar: ChanBar, modules: _ChanPyModules) -> Any:
    if bar.timestamp is not None:
        return modules.CTime(
            bar.timestamp.year,
            bar.timestamp.month,
            bar.timestamp.day,
            bar.timestamp.hour,
            bar.timestamp.minute,
            bar.timestamp.second,
            auto=False,
        )
    return modules.CTime(
        bar.trade_date.year,
        bar.trade_date.month,
        bar.trade_date.day,
        0,
        0,
    )


def _extract_fractals(
    kline_list: Any,
    bars: tuple[ChanBar, ...],
    modules: _ChanPyModules,
) -> list[ChanFractal]:
    fractals: list[ChanFractal] = []
    for klc in kline_list.lst:
        if klc.fx == modules.FX_TYPE.TOP:
            peak_klu = klc.get_peak_klu(is_high=True)
            bar = _bar_for_klu(peak_klu, bars)
            fractals.append(
                ChanFractal(
                    index=bar.index,
                    bar_time=bar.bar_time,
                    trade_date=bar.trade_date,
                    timestamp=bar.timestamp,
                    kind="top",
                    price=decimal_value(peak_klu.high),
                    status=_edge_status(peak_klu.idx, len(bars)),
                )
            )
        elif klc.fx == modules.FX_TYPE.BOTTOM:
            peak_klu = klc.get_peak_klu(is_high=False)
            bar = _bar_for_klu(peak_klu, bars)
            fractals.append(
                ChanFractal(
                    index=bar.index,
                    bar_time=bar.bar_time,
                    trade_date=bar.trade_date,
                    timestamp=bar.timestamp,
                    kind="bottom",
                    price=decimal_value(peak_klu.low),
                    status=_edge_status(peak_klu.idx, len(bars)),
                )
            )
    return fractals


def _extract_strokes(kline_list: Any, bars: tuple[ChanBar, ...]) -> list[ChanStroke]:
    return [_stroke_from_bi(bi, bars) for bi in kline_list.bi_list]


def _stroke_from_bi(bi: Any, bars: tuple[ChanBar, ...]) -> ChanStroke:
    begin_klu = bi.get_begin_klu()
    end_klu = bi.get_end_klu()
    begin_bar = _bar_for_klu(begin_klu, bars)
    end_bar = _bar_for_klu(end_klu, bars)
    direction: ChanDirection = "down" if bi.is_down() else "up"
    return ChanStroke(
        start_index=begin_bar.index,
        end_index=end_bar.index,
        start_time=begin_bar.bar_time,
        end_time=end_bar.bar_time,
        direction=direction,
        price_low=decimal_value(bi._low()),
        price_high=decimal_value(bi._high()),
        status=_status_from_is_sure(bool(bi.is_sure)),
    )


def _extract_segments(
    kline_list: Any,
    bars: tuple[ChanBar, ...],
    modules: _ChanPyModules,
) -> list[ChanSegment]:
    segments: list[ChanSegment] = []
    for segment in kline_list.seg_list:
        begin_klu = segment.get_begin_klu()
        end_klu = segment.get_end_klu()
        begin_bar = _bar_for_klu(begin_klu, bars)
        end_bar = _bar_for_klu(end_klu, bars)
        segments.append(
            ChanSegment(
                start_index=begin_bar.index,
                end_index=end_bar.index,
                start_time=begin_bar.bar_time,
                end_time=end_bar.bar_time,
                direction=_direction_from_bi_dir(segment.dir, modules),
                price_low=decimal_value(segment._low()),
                price_high=decimal_value(segment._high()),
                status=_status_from_is_sure(bool(segment.is_sure)),
                stroke_indexes=tuple(
                    bi.idx for bi in segment.bi_list
                )
                or tuple(range(segment.start_bi.idx, segment.end_bi.idx + 1)),
            )
        )
    return segments


def _extract_centers(kline_list: Any, bars: tuple[ChanBar, ...]) -> list[ChanCenter]:
    centers: list[ChanCenter] = []
    for center in kline_list.zs_list:
        begin_bar = _bar_for_klu(center.begin, bars)
        end_bar = _bar_for_klu(center.end, bars)
        centers.append(
            ChanCenter(
                start_index=begin_bar.index,
                end_index=end_bar.index,
                start_time=begin_bar.bar_time,
                end_time=end_bar.bar_time,
                price_low=decimal_value(center.low),
                price_high=decimal_value(center.high),
                status=_status_from_is_sure(bool(center.is_sure)),
                stroke_indexes=tuple(
                    range(center.begin_bi.idx, center.end_bi.idx + 1)
                ),
            )
        )
    return centers


def _extract_observations(
    kline_list: Any,
    bars: tuple[ChanBar, ...],
) -> list[ChanObservation]:
    observations: list[ChanObservation] = []
    for bsp in kline_list.bs_point_lst.getSortedBspList():
        bar = _bar_for_klu(bsp.klu, bars)
        side: ChanObservationSide = "buy" if bool(bsp.is_buy) else "sell"
        prefix = "B" if side == "buy" else "S"
        kind = "/".join(f"{prefix}{bs_type.value.upper()}" for bs_type in bsp.type)
        observations.append(
            ChanObservation(
                index=bar.index,
                bar_time=bar.bar_time,
                trade_date=bar.trade_date,
                timestamp=bar.timestamp,
                kind=kind,
                side=side,
                label=f"{kind} observation",
                price=decimal_value(bsp.klu.low if side == "buy" else bsp.klu.high),
                status=_status_from_is_sure(bool(bsp.bi.is_sure)),
                explanation=(
                    f"{kind} generated by Vespa314/chan.py morphological "
                    "buy/sell point rules. This is informational research, "
                    "not financial advice."
                ),
            )
        )
    return observations


def _direction_from_bi_dir(direction: Any, modules: _ChanPyModules) -> ChanDirection:
    if direction == modules.BI_DIR.DOWN:
        return "down"
    if direction == modules.BI_DIR.UP:
        return "up"
    return "neutral"


def _bar_for_klu(klu: Any, bars: tuple[ChanBar, ...]) -> ChanBar:
    idx = int(klu.idx)
    if 0 <= idx < len(bars):
        return bars[idx]
    return bars[-1]


def _edge_status(index: int, bar_count: int) -> ChanElementStatus:
    return "confirmed" if index < bar_count - 2 else "provisional"


def _status_from_is_sure(is_sure: bool) -> ChanElementStatus:
    return "confirmed" if is_sure else "provisional"
