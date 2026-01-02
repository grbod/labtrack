import { Link } from "react-router-dom"
import {
  Package,
  TestTube,
  CheckSquare,
  FileText,
  TrendingUp,
  Clock,
  FlaskConical,
  Loader2,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

import { useProducts } from "@/hooks/useProducts"
import { useLots, useLotStatusCounts } from "@/hooks/useLots"
import { usePendingReviewCount } from "@/hooks/useTestResults"

interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon: React.ReactNode
  isLoading?: boolean
}

function StatCard({ title, value, description, icon, isLoading }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className="text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        ) : (
          <>
            <div className="text-2xl font-bold">{value}</div>
            {description && (
              <p className="text-xs text-muted-foreground">{description}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
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
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your COA management system
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Products"
          value={productsData?.total ?? 0}
          description="Active in catalog"
          icon={<Package className="h-4 w-4" />}
          isLoading={productsLoading}
        />
        <StatCard
          title="Active Samples"
          value={activeSamples}
          description="In progress"
          icon={<TestTube className="h-4 w-4" />}
          isLoading={statusLoading}
        />
        <StatCard
          title="Pending Approvals"
          value={pendingApprovals}
          description="Awaiting review"
          icon={<CheckSquare className="h-4 w-4" />}
          isLoading={pendingLoading}
        />
        <StatCard
          title="Ready to Publish"
          value={statusCounts?.approved ?? 0}
          description="Approved lots"
          icon={<FileText className="h-4 w-4" />}
          isLoading={statusLoading}
        />
      </div>

      {/* Quick Actions & Recent Activity */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            <Link
              to="/samples"
              className="flex items-center gap-3 rounded-md border p-3 hover:bg-accent transition-colors"
            >
              <TestTube className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Create New Sample</p>
                <p className="text-xs text-muted-foreground">Start a new lot submission</p>
              </div>
            </Link>
            <Link
              to="/import"
              className="flex items-center gap-3 rounded-md border p-3 hover:bg-accent transition-colors"
            >
              <TrendingUp className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Import Results</p>
                <p className="text-xs text-muted-foreground">Upload PDF or enter manually</p>
              </div>
            </Link>
            <Link
              to="/approvals"
              className="flex items-center gap-3 rounded-md border p-3 hover:bg-accent transition-colors"
            >
              <CheckSquare className="h-5 w-5 text-primary" />
              <div>
                <p className="font-medium text-sm">Review Approvals</p>
                <p className="text-xs text-muted-foreground">{pendingApprovals} pending</p>
              </div>
            </Link>
          </CardContent>
        </Card>

        {/* Recent Lots */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Recent Lots</CardTitle>
          </CardHeader>
          <CardContent>
            {lotsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : lotsData?.items.length === 0 ? (
              <p className="text-center text-muted-foreground py-4">
                No lots yet. <Link to="/samples" className="text-primary hover:underline">Create one</Link>
              </p>
            ) : (
              <div className="space-y-3">
                {lotsData?.items.slice(0, 5).map((lot) => (
                  <div key={lot.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FlaskConical className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-sm font-mono">{lot.reference_number}</p>
                        <p className="text-xs text-muted-foreground">{lot.lot_number}</p>
                      </div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      lot.status === "PENDING"
                        ? "bg-yellow-100 text-yellow-800"
                        : lot.status === "APPROVED"
                        ? "bg-green-100 text-green-800"
                        : lot.status === "RELEASED"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-gray-100 text-gray-800"
                    }`}>
                      {lot.status.toLowerCase()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
