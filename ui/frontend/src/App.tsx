import { createBrowserRouter, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  ArrowUpRight,
  BadgeCheck,
  CalendarClock,
  ChartNoAxesColumn,
  FileSearch,
  Files,
  Landmark,
  SearchCheck,
  Settings,
} from 'lucide-react'
import { StatusPill } from './components/status-pill'
import { useStatusQuery } from './lib/api'
import { ComingNextScreen } from './screens/coming-next-screen'
import { ImportScreen } from './screens/import-screen'
import { OverviewScreen } from './screens/overview-screen'
import { TaxYearsScreen } from './screens/tax-years-screen'

type NavItem = {
  label: string
  path: string
  description: string
  icon: typeof ChartNoAxesColumn
}

const navItems: NavItem[] = [
  {
    label: 'Overview',
    path: '/',
    description: 'Current safety and next step',
    icon: ChartNoAxesColumn,
  },
  {
    label: 'Import',
    path: '/import',
    description: 'Check source CSV files',
    icon: Files,
  },
  {
    label: 'Tax Years',
    path: '/tax-years',
    description: 'Policy, filing, and reconciliation',
    icon: CalendarClock,
  },
  {
    label: 'Sales Review',
    path: '/sales-review',
    description: 'Evidence packets are next',
    icon: SearchCheck,
  },
  {
    label: 'Open Positions',
    path: '/open-positions',
    description: 'Residual holdings and warnings',
    icon: BadgeCheck,
  },
  {
    label: 'FX Rates',
    path: '/fx',
    description: 'Defensible rate sourcing',
    icon: Landmark,
  },
  {
    label: 'Audit Pack',
    path: '/audit',
    description: 'Exports and traceability',
    icon: FileSearch,
  },
  {
    label: 'Settings',
    path: '/settings',
    description: 'Project and tolerance knobs',
    icon: Settings,
  },
]

function Sidebar() {
  const location = useLocation()

  return (
    <aside className="flex w-full shrink-0 flex-col gap-6 rounded-[2rem] border border-white/60 bg-white/75 p-5 shadow-[0_30px_80px_rgba(44,54,39,0.10)] backdrop-blur lg:w-[292px]">
      <div className="space-y-3">
        <div className="inline-flex items-center rounded-full border border-stone-200/80 bg-stone-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">
          Stock Tax Cockpit
        </div>
        <div>
          <h1 className="font-display text-2xl text-stone-900">Operator workspace</h1>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Calm, local-first workflow for validating stock-tax outputs without turning the UI into a spreadsheet.
          </p>
        </div>
      </div>

      <nav className="grid gap-2">
        {navItems.map((item) => {
          const active = location.pathname === item.path
          const Icon = item.icon

          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`group rounded-[1.4rem] border px-4 py-3 transition duration-200 ${
                active
                  ? 'border-stone-900 bg-stone-900 text-stone-50 shadow-[0_18px_40px_rgba(28,25,23,0.22)]'
                  : 'border-transparent bg-stone-50/70 text-stone-700 hover:border-stone-200 hover:bg-white'
              }`}
            >
              <div className="flex items-start gap-3">
                <div
                  className={`mt-0.5 rounded-xl p-2 ${
                    active ? 'bg-white/10 text-stone-50' : 'bg-stone-900/5 text-stone-600'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold">{item.label}</div>
                  <p className={`mt-1 text-xs leading-5 ${active ? 'text-stone-300' : 'text-stone-500'}`}>
                    {item.description}
                  </p>
                </div>
              </div>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

function AppFrame() {
  const { data: status } = useStatusQuery()

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(236,253,245,0.9),_transparent_34%),radial-gradient(circle_at_top_right,_rgba(254,249,195,0.55),_transparent_28%),linear-gradient(180deg,_#f7f4ee_0%,_#f2eee7_45%,_#ece7df_100%)] px-4 py-4 text-stone-900 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-[1500px] flex-col gap-4 lg:flex-row">
        <Sidebar />
        <main className="flex min-h-[70vh] flex-1 flex-col rounded-[2rem] border border-white/60 bg-[rgba(255,252,248,0.86)] p-4 shadow-[0_36px_80px_rgba(61,52,45,0.12)] backdrop-blur sm:p-6">
          <header className="mb-6 flex flex-col gap-4 border-b border-stone-200/80 pb-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Frontend foundation</p>
              <h2 className="mt-2 font-display text-3xl text-stone-900">Desktop calm, backend truth</h2>
              <p className="mt-3 max-w-3xl text-sm leading-6 text-stone-600">
                The implemented screens below read real data from FastAPI. Workbook logic stays on the server, and filed 2024 remains frozen as LIFO.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[1.5rem] border border-stone-200/80 bg-white/80 px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">API status</div>
                <div className="mt-2 flex items-center gap-3">
                  <StatusPill status={status?.global_status ?? 'needs_review'} />
                  <span className="text-sm text-stone-600">{status?.last_calculated_at ? 'Connected to live backend' : 'Waiting for backend response'}</span>
                </div>
              </div>
              <div className="rounded-[1.5rem] border border-stone-200/80 bg-white/80 px-4 py-3">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Contract</div>
                <div className="mt-2 flex items-center justify-between gap-3 text-sm text-stone-600">
                  <span>No frontend Excel parsing</span>
                  <ArrowUpRight className="h-4 w-4 text-stone-400" />
                </div>
              </div>
            </div>
          </header>
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function comingNext(title: string, description: string) {
  return <ComingNextScreen title={title} description={description} />
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppFrame />,
    children: [
      { index: true, element: <OverviewScreen /> },
      { path: 'import', element: <ImportScreen /> },
      { path: 'tax-years', element: <TaxYearsScreen /> },
      {
        path: 'sales-review',
        element: comingNext(
          'Sales Review',
          'Evidence packets and per-sale review tools will land here next, after the first three screens.',
        ),
      },
      {
        path: 'open-positions',
        element: comingNext(
          'Open Positions',
          'The layout is reserved for residual holdings and reconciliation warnings.',
        ),
      },
      {
        path: 'fx',
        element: comingNext(
          'FX Rates',
          'FX sourcing cards and year-level provenance will be added on this foundation.',
        ),
      },
      {
        path: 'audit',
        element: comingNext(
          'Audit Pack',
          'Audit exports and trace counters are intentionally deferred until after the core read-only flow.',
        ),
      },
      {
        path: 'settings',
        element: comingNext(
          'Settings',
          'Project path controls and tolerance tuning stay reserved here for the next milestone.',
        ),
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
