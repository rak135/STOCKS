import { createBrowserRouter, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  CalendarClock,
  ChartNoAxesColumn,
  CheckCircle2,
  FileSearch,
  Files,
  FolderOpen,
  Landmark,
  LoaderCircle,
  RefreshCw,
  SearchCheck,
  Settings,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react'
import type { ComponentType, SVGProps } from 'react'
import { Button, Chip, StatusDot } from './components/ui'
import { ApiError, useRecalculateMutation, useStatusQuery } from './lib/api'
import { AuditScreen } from './screens/audit-screen'
import { FxScreen } from './screens/fx-screen'
import { ImportScreen } from './screens/import-screen'
import { OpenPositionsScreen } from './screens/open-positions-screen'
import { OverviewScreen } from './screens/overview-screen'
import { SalesReviewScreen } from './screens/sales-review-screen'
import { SettingsScreen } from './screens/settings-screen'
import { TaxYearsScreen } from './screens/tax-years-screen'
import { compactPath, formatDateTime } from './lib/format'

type IconCmp = ComponentType<SVGProps<SVGSVGElement>>

type NavItem = {
  label: string
  path: string
  icon: IconCmp
}

const navItems: NavItem[] = [
  { label: 'Overview', path: '/', icon: ChartNoAxesColumn },
  { label: 'Import', path: '/import', icon: Files },
  { label: 'Tax Years', path: '/tax-years', icon: CalendarClock },
  { label: 'Sales Review', path: '/sales-review', icon: SearchCheck },
  { label: 'Open Positions', path: '/open-positions', icon: TrendingUp },
  { label: 'FX Rates', path: '/fx', icon: Landmark },
  { label: 'Audit Pack', path: '/audit', icon: FileSearch },
  { label: 'Settings', path: '/settings', icon: Settings },
]

function Sidebar({ projectPath, lastCalculated }: { projectPath: string | null; lastCalculated: string | null }) {
  const location = useLocation()

  return (
    <aside className="w-60 shrink-0 border-r border-borderc bg-surface flex flex-col">
      <div className="px-4 pt-5 pb-4">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-accent text-white grid place-items-center text-[11px] font-semibold">
            CZ
          </div>
          <div className="leading-tight">
            <div className="text-[13px] font-semibold text-ink">Stocks Tax</div>
            <div className="text-[11px] text-ink3">Operator cockpit</div>
          </div>
        </div>
      </div>

      <nav className="px-2 py-2 flex-1 overflow-auto">
        {navItems.map((item) => {
          const active = location.pathname === item.path
          const Icon = item.icon
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] focus-ring ${
                active
                  ? 'bg-accent-bg text-ink font-medium'
                  : 'text-ink2 hover:bg-borderc/40 hover:text-ink'
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      <div className="px-4 py-3 border-t border-borderc text-[11px] text-ink3 space-y-0.5">
        <div className="truncate" title={projectPath ?? undefined}>
          {projectPath ? compactPath(projectPath) : 'No project path'}
        </div>
        <div>Last calc {lastCalculated ? formatDateTime(lastCalculated) : '—'}</div>
      </div>
    </aside>
  )
}

function TopBar() {
  const { data: status } = useStatusQuery()
  const recalculate = useRecalculateMutation()
  const tone = status
    ? ({ ready: 'ok', needs_review: 'warn', blocked: 'err' } as const)[status.global_status]
    : 'neutral'
  const label = status
    ? ({ ready: 'Ready', needs_review: 'Needs review', blocked: 'Blocked' } as const)[status.global_status]
    : 'Loading…'
  const projectName = status?.project_path ? compactPath(status.project_path) : 'Stocks Tax'

  const mutationError = recalculate.error
  const errorText =
    mutationError instanceof ApiError
      ? `Recalculation failed (HTTP ${mutationError.status}${mutationError.detail ? `: ${mutationError.detail}` : ''})`
      : 'Recalculation failed.'

  async function handleRecalculate() {
    recalculate.reset()
    await recalculate.mutateAsync()
  }

  return (
    <header className="flex items-center justify-between border-b border-borderc bg-surface/90 backdrop-blur px-6 h-16 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <div className="text-[13px] text-ink2">Project</div>
        <div className="text-[14px] font-medium text-ink truncate">{projectName}</div>
        <Chip tone={tone}>
          {status ? <StatusDot status={status.global_status} /> : null}
          {label}
        </Chip>
      </div>
      <div className="flex flex-col items-end gap-1">
        <div className="flex items-center gap-2">
        <Button variant="secondary" disabled title="Open CSV folder is a backend integration; reserved.">
          <FolderOpen className="w-4 h-4" />
          Open CSV folder
        </Button>
          <Button
            variant="secondary"
            disabled={recalculate.isPending}
            title="Recalculate from current project data. Runs backend calculation and refreshes app data."
            onClick={() => {
              void handleRecalculate()
            }}
          >
            {recalculate.isPending ? (
              <LoaderCircle className="w-4 h-4 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4" />
            )}
            {recalculate.isPending ? 'Recalculating...' : 'Recalculate'}
          </Button>
        </div>
        {recalculate.isSuccess ? (
          <div className="text-[11px] text-ok inline-flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" />
            Recalculation completed. App data refreshed.
          </div>
        ) : null}
        {recalculate.isError ? (
          <div className="text-[11px] text-err inline-flex items-center gap-1" role="alert" aria-live="polite">
            <TriangleAlert className="w-3 h-3" />
            {errorText}
          </div>
        ) : null}
      </div>
    </header>
  )
}

function AppFrame() {
  const { data: status } = useStatusQuery()

  return (
    <div className="h-screen flex bg-bg text-ink">
      <Sidebar projectPath={status?.project_path ?? null} lastCalculated={status?.last_calculated_at ?? null} />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        <main className="flex-1 min-h-0 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppFrame />,
    children: [
      { index: true, element: <OverviewScreen /> },
      { path: 'import', element: <ImportScreen /> },
      { path: 'tax-years', element: <TaxYearsScreen /> },
      { path: 'sales-review', element: <SalesReviewScreen /> },
      { path: 'open-positions', element: <OpenPositionsScreen /> },
      { path: 'fx', element: <FxScreen /> },
      { path: 'audit', element: <AuditScreen /> },
      { path: 'settings', element: <SettingsScreen /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
