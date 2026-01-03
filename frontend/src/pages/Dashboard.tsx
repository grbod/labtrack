import { Link } from "react-router-dom"
import {
  Package,
  TestTube,
  CheckSquare,
  FileText,
  ArrowRight,
  FlaskConical,
  Loader2,
  TrendingUp,
} from "lucide-react"

import { useProducts } from "@/hooks/useProducts"
import { useLots, useLotStatusCounts } from "@/hooks/useLots"
import { usePendingReviewCount } from "@/hooks/useTestResults"

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon: React.ReactNode
  iconBg: string
  isLoading?: boolean
}

function StatCard({ title, value, subtitle, icon, iconBg, isLoading }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] hover:shadow-[0_4px_12px_0_rgba(0,0,0,0.05)] transition-shadow duration-200">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[13px] font-medium text-slate-500 tracking-wide">{title}</p>
          {isLoading ? (
            <Loader2 className="mt-3 h-7 w-7 animate-spin text-slate-300" />
          ) : (
            <p className="mt-2 text-[32px] font-bold text-slate-900 leading-none tracking-tight">{value}</p>
          )}
          {subtitle && !isLoading && (
            <p className="mt-1.5 text-[13px] text-slate-500">{subtitle}</p>
          )}
        </div>
        <div className={`rounded-xl ${iconBg} p-3 shadow-sm`}>
          {icon}
        </div>
      </div>
    </div>
  )
}

export function DashboardPage() {
  const { data: productsData, isLoading: productsLoading } = useProducts({ page_size: 1 })
  const { data: lotsData, isLoading: lotsLoading } = useLots({ page_size: 5 })
  const { data: statusCounts, isLoading: statusLoading } = useLotStatusCounts()
  const { data: pendingCount, isLoading: pendingLoading } = usePendingReviewCount()

  const pendingApprovals = pendingCount?.pending_count ?? 0
  const activeSamples = (statusCounts?.pending ?? 0) + (statusCounts?.partial_results ?? 0) + (statusCounts?.under_review ?? 0)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-[26px] font-bold text-slate-900 tracking-tight">Dashboard</h1>
        <p className="mt-1.5 text-[15px] text-slate-500">
          Overview of your quality control workflow
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Products"
          value={productsData?.total ?? 0}
          subtitle="In catalog"
          icon={<Package className="h-5 w-5 text-blue-600" />}
          iconBg="bg-blue-50"
          isLoading={productsLoading}
        />
        <StatCard
          title="Active Samples"
          value={activeSamples}
          subtitle="In progress"
          icon={<TestTube className="h-5 w-5 text-violet-600" />}
          iconBg="bg-violet-50"
          isLoading={statusLoading}
        />
        <StatCard
          title="Pending Review"
          value={pendingApprovals}
          subtitle="Awaiting approval"
          icon={<CheckSquare className="h-5 w-5 text-amber-600" />}
          iconBg="bg-amber-50"
          isLoading={pendingLoading}
        />
        <StatCard
          title="Ready to Publish"
          value={statusCounts?.approved ?? 0}
          subtitle="Approved lots"
          icon={<FileText className="h-5 w-5 text-emerald-600" />}
          iconBg="bg-emerald-50"
          isLoading={statusLoading}
        />
      </div>

      {/* Two Column Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Quick Actions */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-4">
            <h2 className="text-[15px] font-semibold text-slate-900">Quick Actions</h2>
          </div>
          <div className="divide-y divide-slate-100">
            <Link
              to="/samples"
              className="flex items-center justify-between px-6 py-4 hover:bg-slate-50/80 transition-colors group"
            >
              <div className="flex items-center gap-4">
                <div className="rounded-xl bg-blue-50 p-2.5 shadow-sm group-hover:shadow transition-shadow">
                  <TestTube className="h-5 w-5 text-blue-600" />
                </div>
                <div>
                  <p className="font-semibold text-slate-900 text-[14px]">Create New Sample</p>
                  <p className="text-[13px] text-slate-500 mt-0.5">Start a new lot submission</p>
                </div>
              </div>
              <ArrowRight className="h-5 w-5 text-slate-300 group-hover:text-slate-400 group-hover:translate-x-0.5 transition-all" />
            </Link>
            <Link
              to="/import"
              className="flex items-center justify-between px-6 py-4 hover:bg-slate-50/80 transition-colors group"
            >
              <div className="flex items-center gap-4">
                <div className="rounded-xl bg-emerald-50 p-2.5 shadow-sm group-hover:shadow transition-shadow">
                  <TrendingUp className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <p className="font-semibold text-slate-900 text-[14px]">Import Test Results</p>
                  <p className="text-[13px] text-slate-500 mt-0.5">Upload PDF or enter manually</p>
                </div>
              </div>
              <ArrowRight className="h-5 w-5 text-slate-300 group-hover:text-slate-400 group-hover:translate-x-0.5 transition-all" />
            </Link>
            <Link
              to="/approvals"
              className="flex items-center justify-between px-6 py-4 hover:bg-slate-50/80 transition-colors group"
            >
              <div className="flex items-center gap-4">
                <div className="rounded-xl bg-amber-50 p-2.5 shadow-sm group-hover:shadow transition-shadow">
                  <CheckSquare className="h-5 w-5 text-amber-600" />
                </div>
                <div>
                  <p className="font-semibold text-slate-900 text-[14px]">Review Approvals</p>
                  <p className="text-[13px] text-slate-500 mt-0.5">{pendingApprovals} items pending review</p>
                </div>
              </div>
              <ArrowRight className="h-5 w-5 text-slate-300 group-hover:text-slate-400 group-hover:translate-x-0.5 transition-all" />
            </Link>
          </div>
        </div>

        {/* Recent Lots */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[0_1px_3px_0_rgba(0,0,0,0.04)] overflow-hidden">
          <div className="border-b border-slate-100 px-6 py-4">
            <h2 className="text-[15px] font-semibold text-slate-900">Recent Lots</h2>
          </div>
          <div className="p-5">
            {lotsLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-7 w-7 animate-spin text-slate-300" />
              </div>
            ) : lotsData?.items.length === 0 ? (
              <div className="py-10 text-center">
                <div className="mx-auto w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center">
                  <FlaskConical className="h-7 w-7 text-slate-400" />
                </div>
                <p className="mt-4 text-[14px] font-medium text-slate-600">No lots created yet</p>
                <p className="mt-1 text-[13px] text-slate-500">Get started by creating your first sample</p>
                <Link
                  to="/samples"
                  className="mt-4 inline-flex items-center gap-1.5 text-[13px] font-semibold text-blue-600 hover:text-blue-700 transition-colors"
                >
                  Create your first sample
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            ) : (
              <div className="space-y-2.5">
                {lotsData?.items.slice(0, 5).map((lot) => (
                  <div
                    key={lot.id}
                    className="flex items-center justify-between rounded-lg border border-slate-100 p-3.5 hover:border-slate-200 hover:bg-slate-50/50 transition-all cursor-pointer"
                  >
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-slate-100 p-2">
                        <FlaskConical className="h-4 w-4 text-slate-500" />
                      </div>
                      <div>
                        <p className="text-[13px] font-semibold text-slate-900 font-mono tracking-wide">
                          {lot.reference_number}
                        </p>
                        <p className="text-[12px] text-slate-500 mt-0.5">{lot.lot_number}</p>
                      </div>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${
                        lot.status === "pending"
                          ? "bg-amber-100 text-amber-700"
                          : lot.status === "approved"
                          ? "bg-emerald-100 text-emerald-700"
                          : lot.status === "released"
                          ? "bg-blue-100 text-blue-700"
                          : lot.status === "rejected"
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {lot.status.charAt(0) + lot.status.slice(1).toLowerCase()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Git Hash - Bottom Right */}
      <div className="fixed bottom-4 right-4 text-[11px] text-slate-400 font-mono">
        {__GIT_HASH__}
      </div>
    </div>
  )
}
