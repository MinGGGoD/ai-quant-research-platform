import {
  forwardRef,
  useEffect,
  useEffectEvent,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react'
import type { ForwardedRef } from 'react'
import type { KeyboardEvent, MouseEvent, PointerEvent } from 'react'

import {
  aggregatePrices,
  MOVING_AVERAGE_PERIODS,
  withMovingAverages,
} from '../chartData'
import type {
  ChartInterval,
  ChartPoint,
  MovingAveragePeriod,
} from '../chartData'
import type { ChanAnalysis, DailyPrice } from '../types'

interface KlineChartProps {
  prices: DailyPrice[]
  chanAnalysis?: ChanAnalysis | null
  interval: ChartInterval
  onIntervalChange: (interval: ChartInterval) => void
}

export interface KlineChartHandle {
  focusObservation: (barTime: string) => void
}

interface Crosshair {
  index: number
  y: number
}

interface Viewport {
  key: string
  start: number
  count: number
}

interface DragState {
  pointerId: number
  startClientX: number
  viewportStart: number
}

interface ChanLayerState {
  centers: boolean
  segments: boolean
  strokes: boolean
  observations: boolean
}

const WIDTH = 1040
const HEIGHT = 520
const CHART_TOP = 62
const PRICE_BOTTOM = 366
const VOLUME_TOP = 404
const VOLUME_BOTTOM = 474
const LEFT_PADDING = 24
const RIGHT_PADDING = 76
const MIN_VISIBLE_BARS = 10
const FOCUSED_OBSERVATION_BARS = 40
const INTERVAL_LABELS: Record<ChartInterval, string> = {
  '30m': '30-minute',
  '60m': '60-minute',
  '1D': 'Daily',
  '1W': 'Weekly',
  '1M': 'Monthly',
}
const CHART_INTERVALS = ['30m', '60m', '1D', '1W', '1M'] as const
const CHAN_LAYER_LABELS: Record<keyof ChanLayerState, string> = {
  centers: 'Centers',
  segments: 'Segments',
  strokes: 'Strokes',
  observations: 'B/S',
}
const DEFAULT_CHAN_LAYERS: ChanLayerState = {
  centers: true,
  segments: false,
  strokes: true,
  observations: true,
}
const MA_COLORS: Record<MovingAveragePeriod, string> = {
  5: '#d97706',
  10: '#db2777',
  20: '#2563eb',
  30: '#7c3aed',
  60: '#0f766e',
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

function formatPrice(value: number | null): string {
  return value === null ? '--' : value.toFixed(2)
}

function formatBarLabel(point: DailyPrice): string {
  return point.timestamp
    ? point.timestamp.replace('T', ' ').slice(0, 16)
    : point.trade_date
}

function movingAveragePath(
  points: ChartPoint[],
  period: MovingAveragePeriod,
  xForIndex: (index: number) => number,
  yForPrice: (value: number) => number,
): string {
  let path = ''
  let drawing = false
  points.forEach((point, index) => {
    const value = point.movingAverages[period]
    if (value === null) {
      drawing = false
      return
    }
    path += `${drawing ? ' L' : ' M'} ${xForIndex(index)} ${yForPrice(value)}`
    drawing = true
  })
  return path.trim()
}

function PopulatedKlineChart({
  prices,
  chanAnalysis,
  chartRef,
  interval,
  onIntervalChange,
}: KlineChartProps & { chartRef: ForwardedRef<KlineChartHandle> }) {
  const [crosshair, setCrosshair] = useState<Crosshair | null>(null)
  const [chanLayers, setChanLayers] =
    useState<ChanLayerState>(DEFAULT_CHAN_LAYERS)
  const [viewportState, setViewportState] = useState<Viewport>({
    key: '',
    start: 0,
    count: 0,
  })
  const [isDragging, setIsDragging] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragRef = useRef<DragState | null>(null)
  const allPoints = useMemo(
    () => withMovingAverages(aggregatePrices(prices, interval)),
    [interval, prices],
  )

  const viewportKey = `${interval}:${allPoints.length}:${allPoints[0]?.bar.interval_start}:${allPoints.at(-1)?.bar.interval_start}`
  const minimumVisibleCount = Math.min(MIN_VISIBLE_BARS, allPoints.length)
  const requestedViewport =
    viewportState.key === viewportKey
      ? viewportState
      : {
          key: viewportKey,
          start: 0,
          count: allPoints.length,
        }
  const visibleCount = Math.max(
    minimumVisibleCount,
    Math.min(allPoints.length, requestedViewport.count),
  )
  const maximumStart = Math.max(0, allPoints.length - visibleCount)
  const visibleStart = Math.max(
    0,
    Math.min(maximumStart, requestedViewport.start),
  )
  const points = allPoints.slice(visibleStart, visibleStart + visibleCount)
  const isZoomed = points.length < allPoints.length
  const canZoomIn = points.length > minimumVisibleCount
  const canZoomOut = isZoomed

  const lows = points.map((point) => point.bar.low)
  const highs = points.map((point) => point.bar.high)
  const minimum = Math.min(...lows)
  const maximum = Math.max(...highs)
  const rawRange = maximum - minimum || Math.max(maximum * 0.02, 1)
  const rangePadding = rawRange * 0.08
  const priceMinimum = Math.max(0, minimum - rangePadding)
  const priceMaximum = maximum + rangePadding
  const priceRange = priceMaximum - priceMinimum
  const maximumVolume = Math.max(...points.map((point) => point.bar.volume), 1)
  const chartWidth = WIDTH - LEFT_PADDING - RIGHT_PADDING
  const slotWidth = chartWidth / points.length
  const candleWidth = Math.max(3, Math.min(14, slotWidth * 0.62))
  const xForIndex = (index: number) =>
    LEFT_PADDING + slotWidth * index + slotWidth / 2
  const priceY = (value: number) =>
    CHART_TOP +
    ((priceMaximum - value) / priceRange) * (PRICE_BOTTOM - CHART_TOP)
  const volumeY = (value: number) =>
    VOLUME_BOTTOM - (value / maximumVolume) * (VOLUME_BOTTOM - VOLUME_TOP)
  const gridValues = Array.from(
    { length: 6 },
    (_, index) => priceMaximum - (priceRange * index) / 5,
  )
  const labelIndexes = Array.from(
    new Set(
      Array.from({ length: Math.min(6, points.length) }, (_, index) =>
        Math.round(
          (index * (points.length - 1)) /
            Math.max(1, Math.min(5, points.length - 1)),
        ),
      ),
    ),
  )
  const activeIndex = Math.max(
    0,
    Math.min(points.length - 1, crosshair?.index ?? points.length - 1),
  )
  const activePoint = points[activeIndex]
  const activeBar = activePoint.bar
  const visibleChanAnalysis =
    chanAnalysis &&
    ((interval === '1D' && chanAnalysis.frequency === 'daily') ||
      interval === chanAnalysis.frequency)
      ? chanAnalysis
      : null
  const canShowChanLayers = visibleChanAnalysis !== null
  const allPointIndexByTime = useMemo(
    () =>
      new Map(
        allPoints.map((point, index) => [point.bar.interval_start, index]),
      ),
    [allPoints],
  )
  const visiblePointByTime = new Map(
    points.map((point, index) => [point.bar.interval_start, { index, point }]),
  )
  const xForTime = (time: string) => {
    const match = visiblePointByTime.get(time)
    return match ? xForIndex(match.index) : null
  }
  const previousBar = points[Math.max(0, activeIndex - 1)]?.bar
  const change = previousBar ? activeBar.close - previousBar.close : 0
  const changePercent =
    previousBar && previousBar.close !== 0
      ? (change / previousBar.close) * 100
      : 0

  const updateCrosshair = (event: MouseEvent<SVGSVGElement>) => {
    if (dragRef.current) {
      return
    }
    const bounds = svgRef.current?.getBoundingClientRect()
    if (!bounds || bounds.width === 0 || bounds.height === 0) {
      return
    }
    const x = ((event.clientX - bounds.left) / bounds.width) * WIDTH
    const y = ((event.clientY - bounds.top) / bounds.height) * HEIGHT
    const index = Math.max(
      0,
      Math.min(points.length - 1, Math.floor((x - LEFT_PADDING) / slotWidth)),
    )
    setCrosshair({
      index,
      y: Math.max(CHART_TOP, Math.min(VOLUME_BOTTOM, y)),
    })
  }

  const updateViewport = (count: number, start: number) => {
    const nextCount = Math.max(
      minimumVisibleCount,
      Math.min(allPoints.length, count),
    )
    setViewportState({
      key: viewportKey,
      count: nextCount,
      start: Math.max(0, Math.min(allPoints.length - nextCount, start)),
    })
    setCrosshair(null)
  }

  useImperativeHandle(
    chartRef,
    () => ({
      focusObservation(barTime: string) {
        const targetIndex = allPointIndexByTime.get(barTime)
        if (targetIndex === undefined) {
          return
        }

        const nextCount = Math.max(
          minimumVisibleCount,
          Math.min(allPoints.length, FOCUSED_OBSERVATION_BARS),
        )
        const nextStart = Math.max(
          0,
          Math.min(
            allPoints.length - nextCount,
            targetIndex - Math.floor(nextCount / 2),
          ),
        )
        setViewportState({
          key: viewportKey,
          count: nextCount,
          start: nextStart,
        })
        setCrosshair({
          index: Math.max(0, Math.min(nextCount - 1, targetIndex - nextStart)),
          y: CHART_TOP + (PRICE_BOTTOM - CHART_TOP) / 2,
        })
      },
    }),
    [
      allPointIndexByTime,
      allPoints.length,
      minimumVisibleCount,
      viewportKey,
    ],
  )

  const zoomAt = (direction: 'in' | 'out', anchorRatio = 0.5) => {
    const nextCount =
      direction === 'in'
        ? Math.max(minimumVisibleCount, Math.floor(points.length * 0.8))
        : Math.min(allPoints.length, Math.ceil(points.length * 1.25))
    if (nextCount === points.length) {
      return
    }

    const clampedAnchorRatio = Math.max(0, Math.min(1, anchorRatio))
    const anchorIndex =
      visibleStart + clampedAnchorRatio * Math.max(0, points.length - 1)
    const nextStart = Math.round(
      anchorIndex - clampedAnchorRatio * Math.max(0, nextCount - 1),
    )
    updateViewport(nextCount, nextStart)
  }

  const handleWheel = useEffectEvent((event: globalThis.WheelEvent) => {
    if (event.deltaY === 0) {
      return
    }
    event.preventDefault()
    const bounds = svgRef.current?.getBoundingClientRect()
    const anchorRatio =
      bounds && bounds.width > 0
        ? (event.clientX - bounds.left) / bounds.width
        : 0.5
    zoomAt(event.deltaY < 0 ? 'in' : 'out', anchorRatio)
  })

  useEffect(() => {
    const chart = svgRef.current
    if (!chart) {
      return
    }

    chart.addEventListener('wheel', handleWheel, { passive: false })
    return () => chart.removeEventListener('wheel', handleWheel)
  }, [])

  const startDragging = (event: PointerEvent<SVGSVGElement>) => {
    if (!isZoomed || event.button !== 0) {
      return
    }
    dragRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      viewportStart: visibleStart,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    setIsDragging(true)
    setCrosshair(null)
  }

  const dragViewport = (event: PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    const bounds = svgRef.current?.getBoundingClientRect()
    if (
      !drag ||
      drag.pointerId !== event.pointerId ||
      !bounds ||
      bounds.width === 0
    ) {
      return
    }
    const barsMoved = Math.round(
      ((drag.startClientX - event.clientX) / bounds.width) * points.length,
    )
    updateViewport(points.length, drag.viewportStart + barsMoved)
  }

  const stopDragging = (event: PointerEvent<SVGSVGElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) {
      return
    }
    dragRef.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    setIsDragging(false)
  }

  const moveCrosshairWithKeyboard = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
      return
    }
    event.preventDefault()
    const current = crosshair?.index ?? points.length - 1
    const direction = event.key === 'ArrowLeft' ? -1 : 1
    setCrosshair({
      index: Math.max(0, Math.min(points.length - 1, current + direction)),
      y: priceY(
        points[Math.max(0, Math.min(points.length - 1, current + direction))]
          .bar.close,
      ),
    })
  }

  const crosshairPrice =
    crosshair && crosshair.y <= PRICE_BOTTOM
      ? priceMaximum -
        ((crosshair.y - CHART_TOP) / (PRICE_BOTTOM - CHART_TOP)) * priceRange
      : null

  return (
    <div className="chart-workspace">
      <div className="chart-toolbar">
        <div
          className="interval-selector"
          role="group"
          aria-label="K-line interval"
        >
          {CHART_INTERVALS.map((value) => (
            <button
              className={interval === value ? 'active' : ''}
              key={value}
              onClick={() => {
                onIntervalChange(value)
                setCrosshair(null)
                setViewportState({
                  key: '',
                  start: 0,
                  count: 0,
                })
              }}
              type="button"
              aria-pressed={interval === value}
              title={INTERVAL_LABELS[value]}
            >
              {value}
            </button>
          ))}
        </div>
        <div className="chart-tools">
          <span className="chart-mode-note">
            {INTERVAL_LABELS[interval]} bars | {points.length}/
            {allPoints.length} visible
          </span>
          {canShowChanLayers && (
            <div
              className="chan-layer-controls"
              role="group"
              aria-label="Chan theory layers"
            >
              {(
                Object.keys(CHAN_LAYER_LABELS) as Array<keyof ChanLayerState>
              ).map((layer) => (
                <label key={layer}>
                  <input
                    type="checkbox"
                    checked={chanLayers[layer]}
                    onChange={(event) =>
                      setChanLayers((current) => ({
                        ...current,
                        [layer]: event.target.checked,
                      }))
                    }
                  />
                  <span>{CHAN_LAYER_LABELS[layer]}</span>
                </label>
              ))}
            </div>
          )}
          <div
            className="zoom-controls"
            role="group"
            aria-label="Chart zoom controls"
          >
            <button
              type="button"
              aria-label="Zoom out"
              disabled={!canZoomOut}
              onClick={() => zoomAt('out')}
            >
              -
            </button>
            <button
              type="button"
              aria-label="Zoom in"
              disabled={!canZoomIn}
              onClick={() => zoomAt('in')}
            >
              +
            </button>
            <button
              type="button"
              disabled={!isZoomed}
              onClick={() => updateViewport(allPoints.length, 0)}
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      {prices.length < 60 && (
        <div className="history-notice" role="note">
          Only {prices.length} stored {INTERVAL_LABELS[interval].toLowerCase()}{' '}
          record
          {prices.length === 1 ? '' : 's'}. Import more history to populate
          longer moving averages and meaningful higher-level views.
        </div>
      )}

      <div className="chart-wrap">
        <div className="chart-legend" aria-live="polite">
          <div className="ohlc-line">
            <strong>{formatBarLabel(activeBar)}</strong>
            <span>O {formatPrice(activeBar.open)}</span>
            <span>H {formatPrice(activeBar.high)}</span>
            <span>L {formatPrice(activeBar.low)}</span>
            <span>C {formatPrice(activeBar.close)}</span>
            <span className={change >= 0 ? 'positive' : 'negative'}>
              {change >= 0 ? '+' : ''}
              {change.toFixed(2)} ({changePercent >= 0 ? '+' : ''}
              {changePercent.toFixed(2)}%)
            </span>
          </div>
          <div className="ma-legend">
            {MOVING_AVERAGE_PERIODS.map((period) => (
              <span key={period} style={{ color: MA_COLORS[period] }}>
                MA{period} {formatPrice(activePoint.movingAverages[period])}
              </span>
            ))}
          </div>
        </div>

        <svg
          ref={svgRef}
          className="kline-chart"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          role="img"
          aria-label={
            isZoomed
              ? `${INTERVAL_LABELS[interval]} K-line chart showing ${points.length} of ${allPoints.length} price records`
              : `${INTERVAL_LABELS[interval]} K-line chart with ${allPoints.length} price records`
          }
          tabIndex={0}
          onMouseMove={updateCrosshair}
          onMouseLeave={() => setCrosshair(null)}
          onKeyDown={moveCrosshairWithKeyboard}
          onPointerDown={startDragging}
          onPointerMove={dragViewport}
          onPointerUp={stopDragging}
          onPointerCancel={stopDragging}
          data-dragging={isDragging || undefined}
        >
          <title>
            {INTERVAL_LABELS[interval]} K-line, moving averages, and volume
            chart
          </title>
          {gridValues.map((value) => {
            const y = priceY(value)
            return (
              <g key={value}>
                <line
                  className="chart-grid"
                  x1={LEFT_PADDING}
                  x2={WIDTH - RIGHT_PADDING}
                  y1={y}
                  y2={y}
                />
                <text
                  className="axis-label price-axis-label"
                  x={WIDTH - RIGHT_PADDING + 10}
                  y={y + 4}
                >
                  {value.toFixed(2)}
                </text>
              </g>
            )
          })}

          {canShowChanLayers &&
            chanLayers.centers &&
            visibleChanAnalysis.centers.map((center, index) => {
              const startX = xForTime(center.start_time)
              const endX = xForTime(center.end_time)
              if (startX === null || endX === null) {
                return null
              }
              const top = priceY(center.price_high)
              const bottom = priceY(center.price_low)
              return (
                <g
                  className={`chan-center ${center.status}`}
                  key={`${center.start_time}:${center.end_time}:${index}`}
                >
                  <title>
                    Center {center.status}: {center.price_low.toFixed(2)}-
                    {center.price_high.toFixed(2)}
                  </title>
                  <rect
                    x={Math.min(startX, endX)}
                    y={top}
                    width={Math.max(2, Math.abs(endX - startX))}
                    height={Math.max(2, bottom - top)}
                  />
                </g>
              )
            })}

          {points.map((point, index) => {
            const { bar } = point
            const x = xForIndex(index)
            const rising = bar.close >= bar.open
            const bodyTop = priceY(Math.max(bar.open, bar.close))
            const bodyBottom = priceY(Math.min(bar.open, bar.close))
            const bodyHeight = Math.max(2, bodyBottom - bodyTop)
            const className = rising ? 'candle-up' : 'candle-down'
            const volumeTop = volumeY(bar.volume)

            return (
              <g key={bar.interval_start}>
                <line
                  className={`candle-wick ${className}`}
                  x1={x}
                  x2={x}
                  y1={priceY(bar.high)}
                  y2={priceY(bar.low)}
                />
                <rect
                  className={`candle-body ${className}`}
                  x={x - candleWidth / 2}
                  y={bodyTop}
                  width={candleWidth}
                  height={bodyHeight}
                />
                <rect
                  className={`volume-bar ${className}`}
                  x={x - candleWidth / 2}
                  y={volumeTop}
                  width={candleWidth}
                  height={Math.max(1, VOLUME_BOTTOM - volumeTop)}
                />
              </g>
            )
          })}

          {MOVING_AVERAGE_PERIODS.map((period) => {
            const path = movingAveragePath(points, period, xForIndex, priceY)
            return path ? (
              <path
                className="ma-line"
                d={path}
                key={period}
                style={{ stroke: MA_COLORS[period] }}
              />
            ) : null
          })}

          {canShowChanLayers &&
            chanLayers.segments &&
            visibleChanAnalysis.segments.map((segment, index) => {
              const startX = xForTime(segment.start_time)
              const endX = xForTime(segment.end_time)
              if (startX === null || endX === null) {
                return null
              }
              const startY =
                segment.direction === 'down'
                  ? priceY(segment.price_high)
                  : priceY(segment.price_low)
              const endY =
                segment.direction === 'down'
                  ? priceY(segment.price_low)
                  : priceY(segment.price_high)
              return (
                <g
                  className={`chan-segment ${segment.status}`}
                  key={`${segment.start_time}:${segment.end_time}:${index}`}
                >
                  <title>
                    Segment {segment.direction}, {segment.status}
                  </title>
                  <line x1={startX} x2={endX} y1={startY} y2={endY} />
                </g>
              )
            })}

          {canShowChanLayers &&
            chanLayers.strokes &&
            visibleChanAnalysis.strokes.map((stroke, index) => {
              const startX = xForTime(stroke.start_time)
              const endX = xForTime(stroke.end_time)
              if (startX === null || endX === null) {
                return null
              }
              const startY =
                stroke.direction === 'down'
                  ? priceY(stroke.price_high)
                  : priceY(stroke.price_low)
              const endY =
                stroke.direction === 'down'
                  ? priceY(stroke.price_low)
                  : priceY(stroke.price_high)
              return (
                <g
                  className={`chan-stroke ${stroke.status}`}
                  key={`${stroke.start_time}:${stroke.end_time}:${index}`}
                >
                  <title>
                    Stroke {stroke.direction}, {stroke.status}
                  </title>
                  <line x1={startX} x2={endX} y1={startY} y2={endY} />
                </g>
              )
            })}

          {canShowChanLayers &&
            chanLayers.observations &&
            visibleChanAnalysis.observations.map((observation) => {
              const x = xForTime(observation.bar_time)
              if (x === null) {
                return null
              }
              const rawY =
                observation.side === 'buy'
                  ? priceY(observation.price) + 18
                  : priceY(observation.price) - 18
              const y = Math.max(
                CHART_TOP + 12,
                Math.min(PRICE_BOTTOM - 8, rawY),
              )
              return (
                <g
                  className={`chan-observation ${observation.side} ${observation.status}`}
                  key={`${observation.bar_time}:${observation.kind}`}
                >
                  <title>{observation.explanation}</title>
                  <rect x={x - 12} y={y - 10} width={24} height={16} rx={4} />
                  <text x={x} y={y + 2} textAnchor="middle">
                    {observation.kind}
                  </text>
                </g>
              )
            })}

          <line
            className="chart-separator"
            x1={LEFT_PADDING}
            x2={WIDTH - RIGHT_PADDING}
            y1={VOLUME_TOP - 16}
            y2={VOLUME_TOP - 16}
          />
          <text
            className="axis-label volume-label"
            x={LEFT_PADDING}
            y={VOLUME_TOP - 22}
          >
            Vol {formatCompact(activeBar.volume)}
          </text>
          <text
            className="axis-label"
            x={WIDTH - RIGHT_PADDING + 10}
            y={VOLUME_TOP + 4}
          >
            {formatCompact(maximumVolume)}
          </text>

          {labelIndexes.map((index) => (
            <text
              className="date-label"
              key={points[index].bar.interval_start}
              x={xForIndex(index)}
              y={HEIGHT - 14}
              textAnchor={
                index === 0
                  ? 'start'
                  : index === points.length - 1
                    ? 'end'
                    : 'middle'
              }
            >
              {formatBarLabel(points[index].bar)}
            </text>
          ))}

          {crosshair && (
            <g className="crosshair" aria-hidden="true">
              <line
                x1={xForIndex(activeIndex)}
                x2={xForIndex(activeIndex)}
                y1={CHART_TOP}
                y2={VOLUME_BOTTOM}
              />
              <line
                x1={LEFT_PADDING}
                x2={WIDTH - RIGHT_PADDING}
                y1={crosshair.y}
                y2={crosshair.y}
              />
              <rect
                className="crosshair-label-bg"
                x={WIDTH - RIGHT_PADDING}
                y={crosshair.y - 11}
                width={RIGHT_PADDING}
                height={22}
              />
              <text
                className="crosshair-label"
                x={WIDTH - RIGHT_PADDING + 8}
                y={crosshair.y + 4}
              >
                {crosshairPrice === null
                  ? formatCompact(activeBar.volume)
                  : crosshairPrice.toFixed(2)}
              </text>
              <rect
                className="crosshair-label-bg"
                x={Math.max(
                  LEFT_PADDING,
                  Math.min(
                    WIDTH - RIGHT_PADDING - 84,
                    xForIndex(activeIndex) - 42,
                  ),
                )}
                y={VOLUME_BOTTOM + 8}
                width={84}
                height={22}
              />
              <text
                className="crosshair-label"
                x={Math.max(
                  LEFT_PADDING + 42,
                  Math.min(
                    WIDTH - RIGHT_PADDING - 42,
                    xForIndex(activeIndex),
                  ),
                )}
                y={VOLUME_BOTTOM + 23}
                textAnchor="middle"
              >
                {formatBarLabel(activeBar)}
              </text>
            </g>
          )}
        </svg>
      </div>
    </div>
  )
}

const KlineChart = forwardRef<KlineChartHandle, KlineChartProps>(
  function KlineChart(
    { prices, chanAnalysis, interval, onIntervalChange }: KlineChartProps,
    ref,
  ) {
    if (prices.length === 0) {
      return (
        <div className="empty-state chart-empty">
          No {INTERVAL_LABELS[interval].toLowerCase()} price records are
          available for this stock.
        </div>
      )
    }

    return (
      <PopulatedKlineChart
        prices={prices}
        chanAnalysis={chanAnalysis}
        chartRef={ref}
        interval={interval}
        onIntervalChange={onIntervalChange}
      />
    )
  },
)

export default KlineChart
