import { useQuery } from '@tanstack/react-query'
import {
  FileText,
  CheckCircle,
  Clock,
  AlertTriangle,
  TrendingUp,
  Zap,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from 'recharts'
import { metricsApi, exceptionsApi } from '../services/api'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

export default function Dashboard() {
  const { data: dashboardData, isLoading: dashboardLoading } = useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => metricsApi.getDashboard(30),
  })

  const { data: trendData } = useQuery({
    queryKey: ['trend-metrics'],
    queryFn: () => metricsApi.getTrends(30, 'day'),
  })

  const { data: exceptionMetrics } = useQuery({
    queryKey: ['exception-metrics'],
    queryFn: () => exceptionsApi.getMetrics(),
  })

  if (dashboardLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const kpis = [
    {
      name: 'Total Documents',
      value: dashboardData?.total_documents || 0,
      icon: FileText,
      color: 'text-primary-600',
      bgColor: 'bg-primary-50',
    },
    {
      name: 'Processed',
      value: dashboardData?.kpis?.processed_count || 0,
      icon: CheckCircle,
      color: 'text-success-600',
      bgColor: 'bg-success-50',
    },
    {
      name: 'Pending',
      value: dashboardData?.kpis?.pending_count || 0,
      icon: Clock,
      color: 'text-warning-600',
      bgColor: 'bg-warning-50',
    },
    {
      name: 'Needs Review',
      value: dashboardData?.kpis?.needs_review_count || 0,
      icon: AlertTriangle,
      color: 'text-error-600',
      bgColor: 'bg-error-50',
    },
  ]

  const automationKpis = [
    {
      name: 'Automation Rate',
      value: `${dashboardData?.automation_rate?.toFixed(1) || 0}%`,
      icon: Zap,
      description: 'Documents processed without review',
    },
    {
      name: 'Avg Confidence',
      value: `${dashboardData?.avg_confidence?.toFixed(1) || 0}%`,
      icon: TrendingUp,
      description: 'Average extraction confidence',
    },
  ]

  // Prepare chart data
  const typeData = dashboardData?.documents_by_type
    ? Object.entries(dashboardData.documents_by_type)
        .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }))
        .filter(item => item.value > 0)
    : []

  const processorData = dashboardData?.processor_usage
    ? Object.entries(dashboardData.processor_usage)
        .map(([name, value]) => ({ name: name.replace(/_/g, ' '), value }))
        .filter(item => item.value > 0)
    : []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">Overview of your document processing pipeline</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <div key={kpi.name} className="card p-6">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-lg ${kpi.bgColor}`}>
                <kpi.icon className={`w-6 h-6 ${kpi.color}`} />
              </div>
              <div>
                <p className="text-sm text-gray-500">{kpi.name}</p>
                <p className="text-2xl font-bold text-gray-900">{kpi.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Automation Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {automationKpis.map((kpi) => (
          <div key={kpi.name} className="card p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{kpi.name}</p>
                <p className="text-3xl font-bold text-gray-900">{kpi.value}</p>
                <p className="text-xs text-gray-400 mt-1">{kpi.description}</p>
              </div>
              <kpi.icon className="w-12 h-12 text-primary-200" />
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Trend Chart */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Documents Processed (30 days)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData?.document_trends || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="period"
                  tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  tick={{ fontSize: 12 }}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  labelFormatter={(value) => new Date(value).toLocaleDateString()}
                />
                <Line
                  type="monotone"
                  dataKey="processed"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                  name="Processed"
                />
                <Line
                  type="monotone"
                  dataKey="needs_review"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  name="Needs Review"
                />
                <Line
                  type="monotone"
                  dataKey="failed"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  name="Failed"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Document Types Pie Chart */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Documents by Type
          </h3>
          <div className="h-64">
            {typeData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={typeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {typeData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-400">
                No data available
              </div>
            )}
          </div>
          {typeData.length > 0 && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              {typeData.slice(0, 6).map((item, index) => (
                <div key={item.name} className="flex items-center gap-2 text-sm">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="text-gray-600 truncate">{item.name}</span>
                  <span className="text-gray-400 ml-auto">{item.value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Processor Usage */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Processing Method Distribution
        </h3>
        <div className="h-64">
          {processorData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={processorData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 12 }} width={120} />
                <Tooltip />
                <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400">
              No data available
            </div>
          )}
        </div>
      </div>

      {/* Open Exceptions Summary */}
      {exceptionMetrics && exceptionMetrics.open_count > 0 && (
        <div className="card p-6 border-l-4 border-warning-500">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                Open Exceptions
              </h3>
              <p className="text-gray-500">
                {exceptionMetrics.open_count} exceptions require attention
              </p>
            </div>
            <a
              href="/exceptions"
              className="btn-primary"
            >
              Review Exceptions
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
