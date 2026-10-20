import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  AlertCircle,
  ArrowDownToLine,
  ArrowRight,
  BarChart3,
  Bell,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  CloudUpload,
  Database,
  FileSpreadsheet,
  Layers3,
  PackageCheck,
  RefreshCw,
  Search,
  ShoppingBasket,
  SlidersHorizontal,
  Sparkles,
  Store,
  Upload,
  X,
} from 'lucide-react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Pie,
  PieChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './App.css'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/+$/, '')

type Frequency = 'auto' | 'daily' | 'weekly' | 'monthly'
type ColumnInfo = {
  name: string
  dtype: string
  null_count: number
  null_percentage: number
  unique_count: number
  sample_values: string[]
}
type Profile = {
  filename: string
  rows: number
  columns_count: number
  duplicate_rows: number
  memory_usage_bytes: number
  columns: ColumnInfo[]
  suggestions: {
    suggested_date_column?: string | null
    suggested_target_column?: string | null
  }
}
type Metric = {
  model: string
  mae: number | null
  rmse: number | null
  smape_percent: number | null
  wape_percent: number | null
  status: string
  error?: string | null
}
type ForecastPoint = { date: string; prediction: number }
type HistoryPoint = { date: string; value: number }
type ForecastSeries = {
  group: Record<string, string | number | null>
  best_model: string
  frequency: string
  horizon: number
  history: HistoryPoint[]
  evaluation: Metric[]
  forecast: ForecastPoint[]
  error?: string
}
type ForecastResponse = {
  filename: string
  date_column: string
  target_column: string
  group_columns: string[]
  frequency: string
  rows_dropped: number
  series_count: number
  results: ForecastSeries[]
}
type ChartPoint = {
  date: string
  actual?: number
  forecast?: number
}
type PeriodValue = { period: string; value: number }
type MixValue = { series: string; value: number }
type GroupSort = 'forecast' | 'series'

const GROUP_PAGE_SIZE = 8

const chartColors = ['#63a7ff', '#bc8cff', '#48d7b0', '#ffb86b', '#ff718b']

function groupLabel(group: ForecastSeries['group']) {
  const entries = Object.entries(group)
  return entries.length
    ? entries.map(([key, value]) => `${key}: ${value ?? 'Unknown'}`).join(' / ')
    : 'Overall'
}

function parseDate(value: unknown): Date | null {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value
  if (typeof value !== 'string') return null

  const text = value.trim()
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})/)
  const dmy = text.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/)
  const parsed = iso
    ? new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]))
    : dmy
      ? new Date(Number(dmy[3]), Number(dmy[2]) - 1, Number(dmy[1]))
      : new Date(text)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatDateLabel(value: unknown, options: Intl.DateTimeFormatOptions = {}) {
  const date = parseDate(value)
  return date
    ? new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short', year: 'numeric', ...options }).format(date)
    : '—'
}

function periodCountLabel(count: number, frequency: string) {
  const unit = frequency === 'daily' ? 'day' : frequency === 'weekly' ? 'week' : 'month'
  return `${count} ${unit}${count === 1 ? '' : 's'}`
}

function periodDate(value: unknown, frequency: string): string | null {
  const date = parseDate(value)
  if (!date) return null

  if (frequency === 'weekly') {
    const daysToSunday = (7 - date.getDay()) % 7
    date.setDate(date.getDate() + daysToSunday)
  } else if (frequency === 'monthly') {
    date.setMonth(date.getMonth() + 1, 0)
  }

  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}

function formatCompact(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('en', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

function formatNumber(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return new Intl.NumberFormat('en', { maximumFractionDigits: 2 }).format(value)
}

function csvDownload(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return
  const headers = [...new Set(rows.flatMap((row) => Object.keys(row)))]
  const escapeCell = (value: unknown) =>
    `"${String(value ?? '').replaceAll('"', '""')}"`
  const csv = [
    headers.map(escapeCell).join(','),
    ...rows.map((row) => headers.map((header) => escapeCell(row[header])).join(',')),
  ].join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

async function responseError(response: Response) {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (detail) return JSON.stringify(detail)
  return `Request failed (${response.status})`
}

function App() {
  const fileInput = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [dateColumn, setDateColumn] = useState('')
  const [targetColumn, setTargetColumn] = useState('')
  const [groupColumns, setGroupColumns] = useState<string[]>([])
  const [frequency, setFrequency] = useState<Frequency>('auto')
  const [missingPeriod, setMissingPeriod] = useState<'zero' | 'keep'>('zero')
  const [oneCalendarYear, setOneCalendarYear] = useState(true)
  const [horizon, setHorizon] = useState(30)
  const [forecast, setForecast] = useState<ForecastResponse | null>(null)
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [loadingForecast, setLoadingForecast] = useState(false)
  const [error, setError] = useState('')
  const [selectedSeries, setSelectedSeries] = useState('All groups')
  const [groupSearch, setGroupSearch] = useState('')
  const [groupSort, setGroupSort] = useState<GroupSort>('forecast')
  const [groupPage, setGroupPage] = useState(0)
  const [activeNav, setActiveNav] = useState('Forecasting')
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    let mounted = true
    const checkApi = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`, {
          signal: AbortSignal.timeout(2500),
        })
        if (mounted) setApiOnline(response.ok)
      } catch {
        if (mounted) setApiOnline(false)
      }
    }
    void checkApi()
    const interval = window.setInterval(() => void checkApi(), 15000)
    return () => {
      mounted = false
      window.clearInterval(interval)
    }
  }, [])

  const columns = profile?.columns ?? []
  const dateCandidates = columns.filter((column) => {
    const name = column.name.toLowerCase()
    return name.includes('date') || name.includes('time') || name.includes('period')
  })
  const targetCandidates = columns.filter(
    (column) => column.name !== dateColumn && ['int64', 'float64', 'int32', 'float32'].some(
      (dtype) => column.dtype.includes(dtype),
    ),
  )
  const groupCandidates = columns.filter(
    (column) => column.name !== dateColumn && column.name !== targetColumn,
  )
  const successful = useMemo(
    () => forecast?.results.filter((result) => !result.error) ?? [],
    [forecast],
  )
  const failed = useMemo(
    () => forecast?.results.filter((result) => result.error) ?? [],
    [forecast],
  )

  const chartData = useMemo<ChartPoint[]>(() => {
    if (!forecast) return []
    const rows = new Map<string, ChartPoint>()
    const selectedLabel = selectedSeries

    const add = (date: string, field: 'actual' | 'forecast', value: number) => {
      const point = rows.get(date) ?? { date }
      point[field] = (point[field] ?? 0) + value
      rows.set(date, point)
    }

    for (const result of successful) {
      const label = groupLabel(result.group)
      if (selectedLabel !== 'All groups' && label !== selectedLabel) continue
      for (const point of result.history ?? []) {
        const date = periodDate(point.date, forecast.frequency)
        if (date) add(date, 'actual', Number(point.value))
      }
      for (const point of result.forecast) {
        const date = periodDate(point.date, forecast.frequency)
        if (date) add(date, 'forecast', Number(point.prediction))
      }
    }

    return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date))
  }, [forecast, successful, selectedSeries])

  const groupSummary = useMemo(() => successful.map((result) => {
    const forecastTotal = result.forecast.reduce((sum, point) => sum + Number(point.prediction), 0)
    const peak = result.forecast.reduce<ForecastPoint | null>(
      (highest, point) => !highest || point.prediction > highest.prediction ? point : highest,
      null,
    )
    const comparisonCount = Math.min(result.history?.length ?? 0, result.forecast.length)
    const recentTotal = comparisonCount
      ? result.history.slice(-comparisonCount).reduce((sum, point) => sum + Number(point.value), 0)
      : null
    return {
      series: groupLabel(result.group),
      forecast: forecastTotal,
      recent: recentTotal,
      changePercent: recentTotal && recentTotal > 0
        ? ((forecastTotal - recentTotal) / recentTotal) * 100
        : null,
      peakDate: peak?.date ?? null,
    }
  }).sort((a, b) => b.forecast - a.forecast), [successful])

  const totalForecast = useMemo(
    () => successful.reduce(
      (grandTotal, result) => grandTotal + result.forecast.reduce(
        (seriesTotal, point) => seriesTotal + Number(point.prediction),
        0,
      ),
      0,
    ),
    [successful],
  )

  const forecastHighlights = useMemo(() => {
    let forecastTotal = 0
    let recentTotal = 0
    const valuesByDate = new Map<string, number>()

    for (const result of successful) {
      const forecastValues = result.forecast.map((point) => Number(point.prediction))
      forecastTotal += forecastValues.reduce((sum, value) => sum + value, 0)

      const history = result.history ?? []
      const comparisonCount = Math.min(history.length, forecastValues.length)
      if (comparisonCount > 0) {
        recentTotal += history
          .slice(-comparisonCount)
          .reduce((sum, point) => sum + Number(point.value), 0)
      }

      for (const point of result.forecast) {
        const date = periodDate(point.date, forecast?.frequency ?? 'daily')
        if (date) valuesByDate.set(date, (valuesByDate.get(date) ?? 0) + Number(point.prediction))
      }
    }

    const peak = [...valuesByDate.entries()].reduce<[string, number] | null>(
      (highest, current) => !highest || current[1] > highest[1] ? current : highest,
      null,
    )
    const changePercent = recentTotal > 0
      ? ((forecastTotal - recentTotal) / recentTotal) * 100
      : null

    return { recentTotal, changePercent, peak }
  }, [forecast?.frequency, successful])

  const forecastByMonth = useMemo<PeriodValue[]>(() => {
    if (!forecast) return []
    const monthlyTotals = new Map<string, number>()
    for (const result of successful) {
      for (const point of result.forecast) {
        const date = parseDate(point.date)
        if (!date) continue
        const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
        monthlyTotals.set(month, (monthlyTotals.get(month) ?? 0) + Number(point.prediction))
      }
    }
    return [...monthlyTotals.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([period, value]) => ({ period, value }))
  }, [forecast, successful])

  const seasonalityProfile = useMemo<PeriodValue[]>(() => {
    const monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const byYearMonth = new Map<string, number>()
    for (const result of successful) {
      for (const point of result.history ?? []) {
        const date = parseDate(point.date)
        if (!date) continue
        const key = `${date.getFullYear()}-${date.getMonth()}`
        byYearMonth.set(key, (byYearMonth.get(key) ?? 0) + Number(point.value))
      }
    }

    const yearlyMonths = [...byYearMonth.entries()].map(([key, value]) => {
      const month = Number(key.split('-')[1])
      return { month, value }
    })
    return monthLabels.map((period, month) => {
      const values = yearlyMonths.filter((item) => item.month === month).map((item) => item.value)
      return {
        period,
        value: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0,
      }
    })
  }, [successful])

  const forecastMix = useMemo<MixValue[]>(() => {
    const topGroups = groupSummary.slice(0, 5).map((item) => ({
      series: item.series,
      value: item.forecast,
    }))
    const otherTotal = groupSummary.slice(5).reduce((sum, item) => sum + item.forecast, 0)
    if (otherTotal > 0) topGroups.push({ series: 'Other groups', value: otherTotal })
    return topGroups
  }, [groupSummary])

  const groupComparison = useMemo(() => groupSummary.slice(0, 8), [groupSummary])

  const comparisonPeriods = successful[0]?.horizon ?? 0
  const changePercent = forecastHighlights.changePercent
  const demandDirection = changePercent == null
    ? 'There is not enough recent history to compare demand.'
    : Math.abs(changePercent) < 1
      ? `Demand is expected to stay about the same (${changePercent > 0 ? '+' : ''}${changePercent.toFixed(1)}%) as the previous ${periodCountLabel(comparisonPeriods, forecast?.frequency ?? 'daily')}.`
      : `Demand is expected to be ${Math.abs(changePercent).toFixed(1)}% ${changePercent > 0 ? 'higher' : 'lower'} than the previous ${periodCountLabel(comparisonPeriods, forecast?.frequency ?? 'daily')}.`
  const leadingGroup = forecast?.group_columns.length ? groupSummary[0] : null
  const leadingGroupShare = leadingGroup && totalForecast > 0
    ? leadingGroup.forecast / totalForecast * 100
    : null

  const filteredGroupSummary = useMemo(() => {
    const query = groupSearch.trim().toLocaleLowerCase()
    return groupSummary
      .filter((item) => !query || item.series.toLocaleLowerCase().includes(query))
      .sort((a, b) => {
        if (groupSort === 'series') return a.series.localeCompare(b.series)
        return b.forecast - a.forecast
      })
  }, [groupSearch, groupSort, groupSummary])

  const groupPageCount = Math.ceil(filteredGroupSummary.length / GROUP_PAGE_SIZE)
  const currentGroupPage = Math.min(groupPage, Math.max(groupPageCount - 1, 0))
  const paginatedGroupSummary = filteredGroupSummary.slice(
    currentGroupPage * GROUP_PAGE_SIZE,
    (currentGroupPage + 1) * GROUP_PAGE_SIZE,
  )
  const missingCells = profile?.columns.reduce((sum, column) => sum + column.null_count, 0) ?? 0
  const totalCells = (profile?.rows ?? 0) * (profile?.columns_count ?? 0)
  const completeness = totalCells ? ((totalCells - missingCells) / totalCells) * 100 : null
  const columnsWithMissing = profile?.columns
    .filter((column) => column.null_count > 0)
    .sort((a, b) => b.null_count - a.null_count)
    .slice(0, 4) ?? []

  async function selectFile(nextFile: File | null) {
    if (!nextFile) return
    const extension = nextFile.name.toLowerCase().split('.').pop()
    if (!extension || !['csv', 'xlsx', 'xls'].includes(extension)) {
      setError('Choose a CSV, XLSX, or XLS file.')
      return
    }
    setError('')
    setFile(nextFile)
    setProfile(null)
    setForecast(null)
    setLoadingProfile(true)
    try {
      const form = new FormData()
      form.append('file', nextFile)
      const response = await fetch(`${API_BASE_URL}/profile`, { method: 'POST', body: form })
      if (!response.ok) throw new Error(await responseError(response))
      const nextProfile = (await response.json()) as Profile
      setProfile(nextProfile)
      setDateColumn(nextProfile.suggestions.suggested_date_column ?? '')
      setTargetColumn(nextProfile.suggestions.suggested_target_column ?? '')
      setGroupColumns([])
      setFrequency('auto')
      setSelectedSeries('All groups')
    } catch (cause) {
      setFile(null)
      setError(cause instanceof Error ? cause.message : 'Could not profile this dataset.')
    } finally {
      setLoadingProfile(false)
    }
  }

  async function generateForecast(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    if (!dateColumn || !targetColumn || dateColumn === targetColumn) {
      setError('Choose different date and target columns before forecasting.')
      return
    }
    setError('')
    setLoadingForecast(true)
    setForecast(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('date_column', dateColumn)
      form.append('target_column', targetColumn)
      form.append('group_columns', groupColumns.join(','))
      form.append('frequency', frequency)
      form.append('one_calendar_year', String(oneCalendarYear))
      form.append('missing_period', missingPeriod)
      if (!oneCalendarYear) form.append('horizon', String(horizon))
      const response = await fetch(`${API_BASE_URL}/forecast`, { method: 'POST', body: form })
      if (!response.ok) throw new Error(await responseError(response))
      const result = (await response.json()) as ForecastResponse
      setForecast(result)
      setSelectedSeries('All groups')
      window.setTimeout(() => {
        document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' })
      }, 50)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Forecast generation failed.')
    } finally {
      setLoadingForecast(false)
    }
  }

  function toggleGroup(column: string) {
    setGroupColumns((current) =>
      current.includes(column)
        ? current.filter((item) => item !== column)
        : [...current, column],
    )
  }

  function navigate(label: string, target?: string) {
    setActiveNav(label)
    if (target) document.getElementById(target)?.scrollIntoView({ behavior: 'smooth' })
  }

  const forecastCsvRows = successful.flatMap((result) =>
    result.forecast.map((point) => ({
      ...result.group,
      date: point.date,
      prediction: point.prediction,
    })),
  )

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#top" onClick={() => navigate('Forecasting', 'top')}>
          <span className="brand-mark"><Activity size={20} strokeWidth={2.4} /></span>
          <span className="brand-name">Demand<span>IQ</span></span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <button className={activeNav === 'Overview' ? 'active' : ''} onClick={() => navigate('Overview', 'overview')}>
            <BarChart3 size={17} /> Overview
          </button>
          <button className={activeNav === 'Forecasting' ? 'active' : ''} onClick={() => navigate('Forecasting', 'forecast-setup')}>
            <Activity size={17} /> Demand forecasting
          </button>
          <button className={activeNav === 'Data' ? 'active' : ''} onClick={() => navigate('Data', 'dataset')}>
            <Database size={17} /> Dataset
          </button>
          <button className={activeNav === 'Reports' ? 'active' : ''} onClick={() => navigate('Reports', 'results')}>
            <Layers3 size={17} /> Reports
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="api-indicator">
            <span className={`status-dot ${apiOnline ? 'online' : apiOnline === false ? 'offline' : ''}`} />
            <span>{apiOnline ? 'Forecast API online' : apiOnline === false ? 'API unavailable' : 'Checking API'}</span>
          </div>
          <div className="sidebar-note">
            <Sparkles size={15} />
            <div><strong>Forecast workspace</strong><span>Upload data to get started</span></div>
          </div>
          <div className="profile-chip"><span className="avatar">DI</span><span><strong>Analyst</strong><small>Local workspace</small></span><ChevronDown size={14} /></div>
        </div>
      </aside>

      <main className="main-content" id="top">
        <header className="topbar">
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>Demand forecasting</strong></div>
          <div className="topbar-actions">
            {file && <span className="dataset-pill"><FileSpreadsheet size={14} />{file.name}</span>}
            <button className="icon-button" title="API status" aria-label="API status"><Bell size={17} /></button>
            <button className="icon-button" title="Help" aria-label="Help"><CircleHelp size={17} /></button>
            <span className="avatar avatar-small">DI</span>
          </div>
        </header>

        <div className="page-wrap">
          <section className="page-heading" id="overview">
            <div>
              <div className="eyebrow"><span className="eyebrow-dot" /> FORECAST INTELLIGENCE</div>
              <h1>Demand forecasting</h1>
              <p>Turn your sales history into clear, data-backed plans.</p>
            </div>
            {forecast && (
              <button
                className="button button-secondary"
                onClick={() => csvDownload('demand_forecast.csv', forecastCsvRows)}
              >
                <ArrowDownToLine size={16} /> Export forecast
              </button>
            )}
          </section>

          {error && <div className="error-banner"><AlertCircle size={18} /><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button></div>}

          <section className="upload-row" id="dataset">
            <div
              className={`upload-card ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault()
                setDragging(false)
                void selectFile(event.dataTransfer.files[0] ?? null)
              }}
            >
              <input
                ref={fileInput}
                className="hidden-input"
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(event) => void selectFile(event.target.files?.[0] ?? null)}
              />
              <span className="upload-icon">{file ? <FileSpreadsheet size={20} /> : <CloudUpload size={21} />}</span>
              <div className="upload-copy">
                <strong>{file ? file.name : 'Upload your dataset'}</strong>
                <span>{loadingProfile ? 'Reading columns and data quality…' : file ? 'CSV or Excel · ready to configure' : 'Drop a CSV or Excel file here, or browse to choose one'}</span>
              </div>
              {loadingProfile ? (
                <RefreshCw size={18} className="spin muted-icon" />
              ) : file ? (
                <button className="text-button" onClick={() => { setFile(null); setProfile(null); setForecast(null); setError('') }}>Change file</button>
              ) : (
                <button className="button button-secondary" onClick={() => fileInput.current?.click()}><Upload size={15} /> Browse files</button>
              )}
            </div>
            {profile && (
              <div className="file-summary">
                <div><span>ROWS</span><strong>{profile.rows.toLocaleString()}</strong></div>
                <div><span>COLUMNS</span><strong>{profile.columns_count}</strong></div>
                <div><span>MISSING CELLS</span><strong>{profile.columns.reduce((sum, column) => sum + column.null_count, 0).toLocaleString()}</strong></div>
              </div>
            )}
          </section>

          {profile && (
            <section className="config-panel" id="forecast-setup">
              <div className="section-title-row">
                <div>
                  <div className="section-kicker">SETUP</div>
                  <h2>Configure your forecast</h2>
                  <p>Confirm your dataset fields and forecasting options.</p>
                </div>
                <span className="step-badge"><SlidersHorizontal size={14} /> Forecast settings</span>
              </div>

              <form onSubmit={generateForecast}>
                <div className="config-grid">
                  <label className="field">
                    <span>Date column {dateColumn && dateColumn === profile.suggestions.suggested_date_column && <em className="field-recommendation">Suggested</em>}</span>
                    <select value={dateColumn} onChange={(event) => { setDateColumn(event.target.value); setGroupColumns((current) => current.filter((item) => item !== event.target.value)) }}>
                      <option value="">Select date field</option>
                      {(dateCandidates.length ? dateCandidates : columns).map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
                    </select>
                    <small className="field-help">Choose when each sale or observation happened.</small>
                  </label>
                  <label className="field">
                    <span>Demand column {targetColumn && targetColumn === profile.suggestions.suggested_target_column && <em className="field-recommendation">Suggested</em>}</span>
                    <select value={targetColumn} onChange={(event) => { setTargetColumn(event.target.value); setGroupColumns((current) => current.filter((item) => item !== event.target.value)) }}>
                      <option value="">Select numeric target</option>
                      {(targetCandidates.length ? targetCandidates : columns).map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
                    </select>
                    <small className="field-help">Choose the number to predict, such as sales or units.</small>
                  </label>
                  <label className="field">
                    <span>Data frequency</span>
                    <select value={frequency} onChange={(event) => setFrequency(event.target.value as Frequency)}>
                      <option value="auto">Auto-detect</option>
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                    </select>
                    <small className="field-help">Auto-detect uses the spacing between dates.</small>
                  </label>
                  <label className="field">
                    <span>Missing periods</span>
                    <select value={missingPeriod} onChange={(event) => setMissingPeriod(event.target.value as 'zero' | 'keep')}>
                      <option value="zero">Fill with zero</option>
                      <option value="keep">Keep missing</option>
                    </select>
                    <small className="field-help">Missing periods are gaps between dates, not blank cells.</small>
                  </label>
                </div>
                <div className="config-lower">
                  <div className="group-field">
                    <div className="field-caption">Separate forecasts by <span>Optional</span></div>
                    <p className="group-help">Choose a store or product for a forecast per group. Leave empty for one combined forecast.</p>
                    <div className="group-options">
                      {groupCandidates.length ? groupCandidates.slice(0, 8).map((column) => (
                        <label className={`group-chip ${groupColumns.includes(column.name) ? 'selected' : ''}`} key={column.name}>
                          <input type="checkbox" checked={groupColumns.includes(column.name)} onChange={() => toggleGroup(column.name)} />
                          {groupColumns.includes(column.name) ? <Check size={13} /> : <Store size={13} />}
                          {column.name}
                        </label>
                      )) : <span className="muted-copy">No grouping columns available</span>}
                      {groupCandidates.length > 8 && <span className="muted-copy">+{groupCandidates.length - 8} more columns</span>}
                    </div>
                  </div>
                  <div className="horizon-field">
                    <div className="field-caption">Forecast horizon</div>
                    <label className="toggle-row">
                      <input type="checkbox" checked={oneCalendarYear} onChange={(event) => setOneCalendarYear(event.target.checked)} />
                      <span className="toggle-ui" />
                      <span>One calendar year</span>
                    </label>
                    {!oneCalendarYear && (
                      <label className="horizon-input">Number of {frequency === 'daily' ? 'days' : frequency === 'monthly' ? 'months' : frequency === 'weekly' ? 'weeks' : 'periods'}
                        <input type="number" min={1} max={5000} value={horizon} onChange={(event) => setHorizon(Number(event.target.value))} />
                      </label>
                    )}
                  </div>
                </div>
                <div className="form-footer">
                  <span className="form-hint"><CircleHelp size={14} /> Forecast accuracy depends on data quality and history length.</span>
                  <button className="button button-primary" type="submit" disabled={loadingForecast || loadingProfile || !apiOnline || !dateColumn || !targetColumn}>
                    {loadingForecast ? <><RefreshCw size={16} className="spin" /> Building forecast…</> : <><Sparkles size={16} /> Generate forecast <ArrowRight size={15} /></>}
                  </button>
                </div>
              </form>
              {!apiOnline && <div className="api-warning"><AlertCircle size={15} /> Start the FastAPI service at <code>{API_BASE_URL}</code> to generate a forecast.</div>}
            </section>
          )}

          {!profile && !loadingProfile && (
            <section className="welcome-panel">
              <div className="welcome-art"><div className="art-grid" /><div className="art-line line-one" /><div className="art-line line-two" /><span className="art-point point-one" /><span className="art-point point-two" /><span className="art-point point-three" /></div>
              <div className="welcome-content">
                <span className="welcome-label"><Sparkles size={13} /> YOUR FORECAST WORKSPACE</span>
                <h2>Make your next move<br />with better demand signals.</h2>
                <p>Start by uploading sales history. We’ll help identify your date, target, and optional store or product groupings.</p>
                <button className="button button-primary" onClick={() => fileInput.current?.click()}><CloudUpload size={16} /> Upload a dataset</button>
              </div>
              <div className="welcome-stats">
                <div><Database size={17} /><strong>CSV & Excel</strong><span>Simple data upload</span></div>
                <div><Activity size={17} /><strong>Understand demand</strong><span>See past and expected trends</span></div>
                <div><PackageCheck size={17} /><strong>Actionable forecast</strong><span>Download your results</span></div>
              </div>
            </section>
          )}

          {profile && (
            <section className={`quality-strip ${missingCells || profile.duplicate_rows ? 'quality-attention' : ''}`}>
              <div className="quality-icon">{missingCells || profile.duplicate_rows ? <AlertCircle size={16} /> : <Check size={16} />}</div>
              <div><strong>{missingCells || profile.duplicate_rows ? 'Dataset inspected · review quality signals' : 'Dataset inspected · no missing or duplicate data'}</strong><span>{profile.filename} · {profile.rows.toLocaleString()} records · {profile.columns_count} fields{completeness == null ? '' : ` · ${completeness.toFixed(1)}% cells complete`}</span></div>
              <button className="text-button" onClick={() => navigate('Data', 'dataset')}>View data details <ArrowRight size={13} /></button>
            </section>
          )}

          {forecast && (
            <section className="results-section" id="results">
              <div className="section-title-row results-heading">
                <div>
                  <div className="section-kicker">LATEST RUN <span className="live-tag"><span /> COMPLETE</span></div>
                  <h2>Forecast overview</h2>
                  <p>{forecast.filename} · {forecast.frequency} predictions · {forecast.group_columns.length ? `${successful.length} groups · ` : ''}{forecast.rows_dropped.toLocaleString()} records skipped</p>
                </div>
                <button className="button button-secondary" onClick={() => csvDownload('demand_forecast.csv', forecastCsvRows)}><ArrowDownToLine size={15} /> Download CSV</button>
              </div>

              <div className="kpi-grid">
                <article className="kpi-card">
                  <div className="kpi-top"><span>Expected demand</span><span className="kpi-icon blue"><ShoppingBasket size={17} /></span></div>
                  <strong className="kpi-value">{formatCompact(totalForecast)}</strong>
                  <span className="kpi-foot">Forecast total · {targetColumn}</span>
                </article>
                <article className="kpi-card">
                  <div className="kpi-top"><span>Demand change</span><span className={`kpi-icon ${forecastHighlights.changePercent != null && forecastHighlights.changePercent < 0 ? 'orange' : 'green'}`}><Activity size={17} /></span></div>
                  <strong className="kpi-value">{forecastHighlights.changePercent == null ? '—' : `${forecastHighlights.changePercent > 0 ? '+' : ''}${forecastHighlights.changePercent.toFixed(1)}%`}</strong>
                  <span className="kpi-foot">{forecastHighlights.changePercent == null ? 'Not enough recent data to compare' : `Compared with the previous ${periodCountLabel(successful[0]?.horizon ?? 0, forecast.frequency)}`}</span>
                </article>
                <article className="kpi-card">
                  <div className="kpi-top"><span>Peak demand period</span><span className="kpi-icon purple"><BarChart3 size={17} /></span></div>
                  <strong className="kpi-value kpi-value-date">{forecastHighlights.peak ? formatDateLabel(forecastHighlights.peak[0], { year: '2-digit' }) : '—'}</strong>
                  <span className="kpi-foot">{forecastHighlights.peak ? `${formatCompact(forecastHighlights.peak[1])} ${targetColumn} expected` : 'No peak period available'}</span>
                </article>
                <article className="kpi-card">
                  <div className="kpi-top"><span>Recent demand</span><span className="kpi-icon purple"><Layers3 size={17} /></span></div>
                  <strong className="kpi-value">{formatCompact(forecastHighlights.recentTotal)}</strong>
                  <span className="kpi-foot">Previous {periodCountLabel(comparisonPeriods, forecast.frequency)} · {targetColumn}</span>
                </article>
              </div>

              {failed.length > 0 && <div className="partial-warning"><AlertCircle size={16} /><span>{failed.length} series could not be forecast.</span><details><summary>Review issues</summary><pre>{failed.map((item) => `${groupLabel(item.group)}: ${item.error}`).join('\n')}</pre></details></div>}

              <section className="plain-summary" aria-label="Forecast summary in plain language">
                <span className="plain-summary-icon"><Sparkles size={16} /></span>
                <div>
                  <strong>In plain language</strong>
                  <p>
                    {`About ${formatNumber(totalForecast)} ${targetColumn} are expected over the next ${periodCountLabel(comparisonPeriods, forecast.frequency)}. ${demandDirection}`}
                    {forecastHighlights.peak && ` The busiest forecast period is ${formatDateLabel(forecastHighlights.peak[0])}, with about ${formatNumber(forecastHighlights.peak[1])} ${targetColumn} expected.`}
                    {leadingGroup && leadingGroupShare != null && ` ${leadingGroup.series} has the largest forecast share at ${leadingGroupShare.toFixed(1)}%.`}
                  </p>
                </div>
              </section>

              <div className="dashboard-grid">
                <article className="panel forecast-panel">
                  <div className="panel-heading">
                    <div><h3>Demand over time</h3><p>Blue is recorded demand; purple is expected demand. All groups shows their combined total.</p></div>
                    <label className="select-compact">Show
                      <select value={selectedSeries} onChange={(event) => setSelectedSeries(event.target.value)}>
                        <option value="All groups">All groups · combined total</option>
                        {successful.map((result) => <option key={groupLabel(result.group)}>{groupLabel(result.group)}</option>)}
                      </select>
                    </label>
                  </div>
                  <div className="chart-legend"><span><i className="legend-line actual" /> Recorded</span><span><i className="legend-line predicted" /> Expected</span><span className="chart-frequency">{selectedSeries === 'All groups' ? 'Combined total' : selectedSeries} · {targetColumn}</span></div>
                  <div className="chart-wrap">
                    {chartData.length ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={chartData} margin={{ top: 12, right: 12, left: 4, bottom: 4 }}>
                          <defs>
                            <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#a376ff" stopOpacity={0.2} />
                              <stop offset="100%" stopColor="#a376ff" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="#222a36" vertical={false} />
                          <XAxis dataKey="date" tickFormatter={(date: string) => formatDateLabel(date, { year: '2-digit' })} tick={{ fill: '#798598', fontSize: 10 }} axisLine={false} tickLine={false} minTickGap={38} />
                          <YAxis tickFormatter={(value: number) => formatCompact(value)} tick={{ fill: '#798598', fontSize: 11 }} axisLine={false} tickLine={false} width={50} />
                          <Tooltip
                            contentStyle={{ background: '#131a25', border: '1px solid #293446', borderRadius: 10, color: '#edf2fb' }}
                            labelStyle={{ color: '#99a5b7', marginBottom: 5 }}
                            formatter={(value, name) => [formatNumber(Number(value)), name === 'actual' ? 'Actual' : 'Forecast']}
                            labelFormatter={(label) => formatDateLabel(label)}
                          />
                          <Line type="monotone" dataKey="actual" name="actual" stroke="#65a9ff" strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} />
                          <Line type="monotone" dataKey="forecast" name="forecast" stroke="#b68aff" strokeWidth={2.2} strokeDasharray="6 5" dot={false} activeDot={{ r: 4 }} />
                        </ComposedChart>
                      </ResponsiveContainer>
                    ) : <div className="chart-empty">No chart points for this selection.</div>}
                  </div>
                  <div className="chart-bottom"><span><span className="chart-dot blue-dot" /> Past {forecast.frequency} demand</span><span><span className="chart-dot purple-dot" /> Future {forecast.frequency} demand</span></div>
                </article>
                {forecast.group_columns.length > 0 && groupComparison.length > 0 && (
                  <article className="panel compare-panel">
                    <div className="panel-heading">
                      <div><h3>Recent vs expected by group</h3><p>Same number of recent and forecast periods · top groups by expected demand</p></div>
                      <span className="panel-icon"><Layers3 size={17} /></span>
                    </div>
                    <div className="compare-legend">
                      <span><i className="compare-swatch recent" /> Recent</span>
                      <span><i className="compare-swatch expected" /> Expected</span>
                    </div>
                    <div className="compare-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={groupComparison} layout="vertical" margin={{ top: 4, right: 14, left: 0, bottom: 0 }}>
                          <CartesianGrid stroke="#222a36" horizontal={false} />
                          <XAxis type="number" tickFormatter={(value: number) => formatCompact(value)} tick={{ fill: '#798598', fontSize: 9 }} axisLine={false} tickLine={false} />
                          <YAxis type="category" dataKey="series" width={88} tick={{ fill: '#aab4c3', fontSize: 9 }} axisLine={false} tickLine={false} />
                          <Tooltip
                            contentStyle={{ background: '#131a25', border: '1px solid #293446', borderRadius: 9, color: '#edf2fb' }}
                            formatter={(value, name) => [formatNumber(Number(value)), name === 'recent' ? 'Recent demand' : 'Expected demand']}
                          />
                          <Bar dataKey="recent" name="recent" fill="#63a7ff" radius={[0, 4, 4, 0]} barSize={8} />
                          <Bar dataKey="forecast" name="forecast" fill="#bc8cff" radius={[0, 4, 4, 0]} barSize={8} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </article>
                )}
              </div>

              <div className="visual-grid">
                <article className="panel visual-panel">
                  <div className="panel-heading">
                    <div><h3>Expected demand by month</h3><p>Forecast totals grouped by calendar month</p></div>
                    <span className="panel-icon"><BarChart3 size={16} /></span>
                  </div>
                  {forecastByMonth.length ? (
                    <div className="visual-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={forecastByMonth} margin={{ top: 14, right: 8, left: 2, bottom: 0 }}>
                          <defs>
                            <linearGradient id="monthlyForecastFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#59a8ff" stopOpacity={0.3} />
                              <stop offset="95%" stopColor="#59a8ff" stopOpacity={0.015} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="#222a36" vertical={false} />
                          <XAxis dataKey="period" tickFormatter={(period: string) => {
                            const [year, month] = period.split('-')
                            return new Date(Number(year), Number(month) - 1).toLocaleString('en', { month: 'short' })
                          }} tick={{ fill: '#798598', fontSize: 9 }} axisLine={false} tickLine={false} minTickGap={15} />
                          <YAxis tickFormatter={(value: number) => formatCompact(value)} tick={{ fill: '#798598', fontSize: 9 }} axisLine={false} tickLine={false} width={45} />
                          <Tooltip
                            contentStyle={{ background: '#131a25', border: '1px solid #293446', borderRadius: 9, color: '#edf2fb' }}
                            formatter={(value) => [formatNumber(Number(value)), targetColumn]}
                            labelFormatter={(period) => {
                              const [year, month] = String(period).split('-')
                              return new Date(Number(year), Number(month) - 1).toLocaleString('en', { month: 'long', year: 'numeric' })
                            }}
                          />
                          <Area type="monotone" dataKey="value" stroke="#65a9ff" strokeWidth={2} fill="url(#monthlyForecastFill)" activeDot={{ r: 4 }} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : <div className="chart-empty">No monthly forecast totals are available.</div>}
                  <div className="visual-caption"><span className="caption-dot blue-dot" /> Forecast total <strong>{forecastByMonth.length} months</strong></div>
                </article>

                <article className="panel visual-panel">
                  <div className="panel-heading">
                    <div><h3>Typical demand by month</h3><p>Average monthly demand in the uploaded history</p></div>
                    <span className="panel-icon season-icon"><Activity size={16} /></span>
                  </div>
                  {seasonalityProfile.some((item) => item.value > 0) ? (
                    <div className="visual-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={seasonalityProfile} margin={{ top: 14, right: 8, left: 2, bottom: 0 }}>
                          <CartesianGrid stroke="#222a36" vertical={false} />
                          <XAxis dataKey="period" tick={{ fill: '#798598', fontSize: 9 }} axisLine={false} tickLine={false} />
                          <YAxis tickFormatter={(value: number) => formatCompact(value)} tick={{ fill: '#798598', fontSize: 9 }} axisLine={false} tickLine={false} width={45} />
                          <Tooltip
                            contentStyle={{ background: '#131a25', border: '1px solid #293446', borderRadius: 9, color: '#edf2fb' }}
                            formatter={(value) => [formatNumber(Number(value)), 'Average monthly total']}
                          />
                          <Bar dataKey="value" fill="#b68aff" radius={[4, 4, 0, 0]} maxBarSize={24} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : <div className="chart-empty">Upload historical dates to see monthly demand patterns.</div>}
                  <div className="visual-caption"><span className="caption-dot purple-dot" /> Historical demand <strong>Jan – Dec</strong></div>
                </article>
              </div>

              {forecast.group_columns.length > 0 && forecastMix.length > 1 && (
                <article className="panel mix-panel">
                  <div className="panel-heading">
                    <div><h3>Forecast contribution by group</h3><p>Share of the forecast horizon by series · top five shown separately</p></div>
                    <span className="panel-icon mix-icon"><Layers3 size={16} /></span>
                  </div>
                  <div className="mix-layout">
                    <div className="mix-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={forecastMix} dataKey="value" nameKey="series" innerRadius="62%" outerRadius="88%" paddingAngle={3} stroke="none">
                            {forecastMix.map((item, index) => <Cell key={item.series} fill={chartColors[index % chartColors.length]} />)}
                          </Pie>
                          <Tooltip
                            contentStyle={{ background: '#131a25', border: '1px solid #293446', borderRadius: 9, color: '#edf2fb' }}
                            formatter={(value) => [formatNumber(Number(value)), 'Forecast total']}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                      <div className="mix-center"><strong>{successful.length}</strong><span>series</span></div>
                    </div>
                    <div className="mix-legend">
                      {forecastMix.map((item, index) => {
                        const total = forecastMix.reduce((sum, group) => sum + group.value, 0)
                        const share = total ? item.value / total * 100 : 0
                        return (
                          <div className="mix-legend-row" key={item.series}>
                            <span className="mix-swatch" style={{ backgroundColor: chartColors[index % chartColors.length] }} />
                            <span className="mix-name">{item.series}</span>
                            <span className="mix-share">{share.toFixed(1)}%</span>
                            <strong>{formatCompact(item.value)}</strong>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </article>
              )}

              <article className="panel table-panel" id="reports">
                <div className="panel-heading table-heading table-heading-wrap">
                  <div><h3>Demand by group</h3><p>See which stores or products are expected to need the most</p></div>
                  <div className="table-actions">
                    <label className="table-search">
                      <Search size={14} />
                      <input
                        type="search"
                        value={groupSearch}
                        placeholder="Search groups"
                        aria-label="Search groups"
                        onChange={(event) => { setGroupSearch(event.target.value); setGroupPage(0) }}
                      />
                    </label>
                    <label className="table-sort">Sort
                      <select value={groupSort} onChange={(event) => { setGroupSort(event.target.value as GroupSort); setGroupPage(0) }}>
                        <option value="forecast">Highest forecast</option>
                        <option value="series">Series name</option>
                      </select>
                    </label>
                    <button className="button button-quiet" onClick={() => csvDownload('forecast_summary.csv', groupSummary.map((row) => ({
                      group: row.series,
                      recent_demand: row.recent,
                      expected_demand: row.forecast,
                      change_percent: row.changePercent,
                      share_of_total_percent: totalForecast > 0 ? row.forecast / totalForecast * 100 : 0,
                      peak_period: row.peakDate,
                    })))}><ArrowDownToLine size={14} /> Export table</button>
                  </div>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead><tr><th>Group</th><th>Recent demand</th><th>Expected demand</th><th>Change</th></tr></thead>
                    <tbody>
                      {paginatedGroupSummary.map((row, index) => (
                        <tr key={row.series}>
                          <td><span className={`table-avatar avatar-${index % 4}`}>{row.series.split(': ').at(-1)?.slice(0, 2).toUpperCase() ?? 'OV'}</span><strong>{row.series}</strong></td>
                          <td className="number-cell">{row.recent == null ? '—' : formatNumber(row.recent)}</td>
                          <td className="number-cell">{formatNumber(row.forecast)}</td>
                          <td className={`number-cell ${row.changePercent != null && row.changePercent < 0 ? 'change-negative' : 'change-positive'}`}>{row.changePercent == null ? '—' : `${row.changePercent > 0 ? '+' : ''}${row.changePercent.toFixed(1)}%`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredGroupSummary.length === 0 ? (
                    <div className="table-more">No forecast groups match “{groupSearch}”.</div>
                  ) : (
                    <div className="table-pagination">
                      <span>Showing {currentGroupPage * GROUP_PAGE_SIZE + 1}–{Math.min((currentGroupPage + 1) * GROUP_PAGE_SIZE, filteredGroupSummary.length)} of {filteredGroupSummary.length} series</span>
                      <div>
                        <button className="icon-button" aria-label="Previous page" disabled={currentGroupPage === 0} onClick={() => setGroupPage(currentGroupPage - 1)}><ChevronLeft size={15} /></button>
                        <span>Page {currentGroupPage + 1} of {Math.max(groupPageCount, 1)}</span>
                        <button className="icon-button" aria-label="Next page" disabled={currentGroupPage + 1 >= groupPageCount} onClick={() => setGroupPage(currentGroupPage + 1)}><ChevronRight size={15} /></button>
                      </div>
                    </div>
                  )}
                </div>
              </article>

              <div className="detail-grid">
                <article className="panel detail-panel">
                  <div className="panel-heading"><div><h3>Dataset health</h3><p>Data quality signals from your upload</p></div><Database size={17} className="muted-icon" /></div>
                  <div className="health-list">
                    <div><span className={`health-check ${missingCells ? 'health-warning' : ''}`}>{missingCells ? <AlertCircle size={12} /> : <Check size={12} />}</span><span>Missing cells</span><strong>{missingCells.toLocaleString()}</strong></div>
                    <div><span className={`health-check ${profile?.duplicate_rows ? 'health-warning' : ''}`}>{profile?.duplicate_rows ? <AlertCircle size={12} /> : <Check size={12} />}</span><span>Duplicate records</span><strong>{profile?.duplicate_rows.toLocaleString()}</strong></div>
                    <div><span className={`health-check ${forecast.rows_dropped ? 'health-warning' : ''}`}>{forecast.rows_dropped ? <AlertCircle size={12} /> : <Check size={12} />}</span><span>Rows excluded from forecast</span><strong>{forecast.rows_dropped.toLocaleString()}</strong></div>
                  </div>
                  {columnsWithMissing.length > 0 && (
                    <div className="missing-columns">
                      <div className="missing-columns-heading">Columns with missing values</div>
                      {columnsWithMissing.map((column) => (
                        <div className="missing-column" key={column.name}>
                          <span title={column.name}>{column.name}</span>
                          <div className="missing-meter" role="meter" aria-label={`${column.name} missing values`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={column.null_percentage}>
                            <i style={{ width: `${Math.min(column.null_percentage, 100)}%` }} />
                          </div>
                          <strong>{column.null_percentage.toFixed(1)}%</strong>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
                <article className="panel detail-panel export-panel">
                  <div className="export-illustration"><FileSpreadsheet size={22} /></div>
                  <div className="export-copy"><h3>Take your forecast with you</h3><p>Download expected demand by date and group to share or use in your planning.</p></div>
                  <button className="button button-primary" onClick={() => csvDownload('demand_forecast.csv', forecastCsvRows)}><ArrowDownToLine size={15} /> Export CSV</button>
                </article>
              </div>
              <footer className="page-footer">Forecasts are estimates based on the uploaded history. Validate outputs before making operational decisions.</footer>
            </section>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
