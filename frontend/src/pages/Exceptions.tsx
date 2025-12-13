import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
  Clock,
  Filter,
  Search,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  FileText,
  ArrowRight,
} from 'lucide-react'
import clsx from 'clsx'
import { exceptionsApi } from '../services/api'
import type { Exception, ExceptionStatus, ExceptionPriority } from '../types'

const statusConfig: Record<ExceptionStatus, { label: string; color: string; icon: typeof AlertTriangle }> = {
  open: { label: 'Open', color: 'badge-warning', icon: AlertTriangle },
  in_review: { label: 'In Review', color: 'badge-primary', icon: Clock },
  resolved: { label: 'Resolved', color: 'badge-success', icon: CheckCircle },
  ignored: { label: 'Ignored', color: 'badge-gray', icon: XCircle },
}

const priorityConfig: Record<ExceptionPriority, { label: string; color: string }> = {
  critical: { label: 'Critical', color: 'text-error-600 bg-error-50' },
  high: { label: 'High', color: 'text-warning-600 bg-warning-50' },
  medium: { label: 'Medium', color: 'text-primary-600 bg-primary-50' },
  low: { label: 'Low', color: 'text-gray-600 bg-gray-100' },
}

export default function Exceptions() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('open')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const [selectedExc, setSelectedExc] = useState<Exception | null>(null)
  const [resolution, setResolution] = useState('')
  const [correctedValue, setCorrectedValue] = useState('')
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  const queryClient = useQueryClient()

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['exceptions', page, statusFilter, priorityFilter, search],
    queryFn: () =>
      exceptionsApi.list({
        page,
        page_size: 20,
        status: statusFilter || undefined,
        priority: priorityFilter || undefined,
        search: search || undefined,
      }),
  })

  const { data: metrics } = useQuery({
    queryKey: ['exception-metrics'],
    queryFn: () => exceptionsApi.getMetrics(),
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { resolution_notes: string; corrected_value?: string } }) =>
      exceptionsApi.resolve(id, data),
    onSuccess: () => {
      toast.success('Exception resolved')
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
      queryClient.invalidateQueries({ queryKey: ['exception-metrics'] })
      setSelectedExc(null)
      setResolution('')
      setCorrectedValue('')
    },
    onError: (error: Error) => {
      toast.error(`Failed to resolve: ${error.message}`)
    },
  })

  const ignoreMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      exceptionsApi.ignore(id, reason),
    onSuccess: () => {
      toast.success('Exception ignored')
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
      queryClient.invalidateQueries({ queryKey: ['exception-metrics'] })
      setSelectedExc(null)
    },
    onError: (error: Error) => {
      toast.error(`Failed to ignore: ${error.message}`)
    },
  })

  const bulkResolveMutation = useMutation({
    mutationFn: (data: { exception_ids: string[]; resolution_notes: string }) =>
      exceptionsApi.bulkResolve(data),
    onSuccess: (result) => {
      toast.success(`${result.resolved_count} exceptions resolved`)
      queryClient.invalidateQueries({ queryKey: ['exceptions'] })
      queryClient.invalidateQueries({ queryKey: ['exception-metrics'] })
      setSelectedIds([])
    },
    onError: (error: Error) => {
      toast.error(`Bulk resolve failed: ${error.message}`)
    },
  })

  const formatDate = (date: string) => {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getAgeLabel = (date: string) => {
    const diffMs = Date.now() - new Date(date).getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
    if (diffDays === 0) return 'Today'
    if (diffDays === 1) return '1 day ago'
    if (diffDays < 7) return `${diffDays} days ago`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
    return `${Math.floor(diffDays / 30)} months ago`
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === data?.items.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(data?.items.map((e) => e.id) || [])
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const handleResolve = () => {
    if (!selectedExc || !resolution.trim()) return
    resolveMutation.mutate({
      id: selectedExc.id,
      data: {
        resolution_notes: resolution,
        corrected_value: correctedValue || undefined,
      },
    })
  }

  const handleIgnore = () => {
    if (!selectedExc) return
    const reason = prompt('Reason for ignoring this exception:')
    if (reason) {
      ignoreMutation.mutate({ id: selectedExc.id, reason })
    }
  }

  const handleBulkResolve = () => {
    if (selectedIds.length === 0) return
    const notes = prompt('Resolution notes for all selected exceptions:')
    if (notes) {
      bulkResolveMutation.mutate({
        exception_ids: selectedIds,
        resolution_notes: notes,
      })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Exceptions</h1>
          <p className="text-gray-500">Review and resolve data extraction issues</p>
        </div>
        <button onClick={() => refetch()} className="btn-secondary">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-warning-50">
                <AlertTriangle className="w-5 h-5 text-warning-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Open</p>
                <p className="text-xl font-bold text-gray-900">{metrics.open_count}</p>
              </div>
            </div>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary-50">
                <Clock className="w-5 h-5 text-primary-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">In Review</p>
                <p className="text-xl font-bold text-gray-900">{metrics.in_review_count}</p>
              </div>
            </div>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-success-50">
                <CheckCircle className="w-5 h-5 text-success-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Resolved Today</p>
                <p className="text-xl font-bold text-gray-900">{metrics.resolved_today}</p>
              </div>
            </div>
          </div>
          <div className="card p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gray-100">
                <Clock className="w-5 h-5 text-gray-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Avg Resolution</p>
                <p className="text-xl font-bold text-gray-900">
                  {metrics.avg_resolution_hours?.toFixed(1) || 0}h
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search exceptions..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            className="input pl-10"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-5 h-5 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            className="input"
          >
            <option value="">All Status</option>
            <option value="open">Open</option>
            <option value="in_review">In Review</option>
            <option value="resolved">Resolved</option>
            <option value="ignored">Ignored</option>
          </select>
          <select
            value={priorityFilter}
            onChange={(e) => {
              setPriorityFilter(e.target.value)
              setPage(1)
            }}
            className="input"
          >
            <option value="">All Priority</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Bulk Actions */}
      {selectedIds.length > 0 && (
        <div className="flex items-center gap-4 p-4 bg-primary-50 rounded-lg">
          <span className="text-sm text-primary-700">
            {selectedIds.length} exception{selectedIds.length > 1 ? 's' : ''} selected
          </span>
          <button
            onClick={handleBulkResolve}
            className="btn-primary text-sm"
            disabled={bulkResolveMutation.isPending}
          >
            Bulk Resolve
          </button>
          <button
            onClick={() => setSelectedIds([])}
            className="btn-secondary text-sm"
          >
            Clear Selection
          </button>
        </div>
      )}

      {/* Exceptions Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-6 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedIds.length === data?.items.length && data?.items.length > 0}
                    onChange={toggleSelectAll}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Exception
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Document
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Age
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
                    Loading exceptions...
                  </td>
                </tr>
              ) : data?.items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                    <CheckCircle className="w-12 h-12 mx-auto mb-2 text-success-300" />
                    No exceptions found
                  </td>
                </tr>
              ) : (
                data?.items.map((exc) => {
                  const status = statusConfig[exc.status]
                  const priority = priorityConfig[exc.priority]
                  const StatusIcon = status.icon
                  return (
                    <tr key={exc.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(exc.id)}
                          onChange={() => toggleSelect(exc.id)}
                          className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                        />
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-medium text-gray-900">
                            {exc.category.replace(/_/g, ' ')}
                          </p>
                          <p className="text-sm text-gray-500 truncate max-w-xs">
                            {exc.field_name}: {exc.reason}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-gray-400" />
                          <span className="text-sm text-gray-600 truncate max-w-[150px]">
                            {exc.document?.original_filename || 'Unknown'}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={clsx(
                            'px-2 py-1 rounded-full text-xs font-medium',
                            priority.color
                          )}
                        >
                          {priority.label}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={clsx('badge', status.color)}>
                          <StatusIcon className="w-3 h-3 mr-1" />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {getAgeLabel(exc.created_at)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => {
                            setSelectedExc(exc)
                            setCorrectedValue(exc.actual_value || '')
                          }}
                          className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
                          title="View details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div className="flex items-center justify-between px-6 py-4 border-t bg-gray-50">
            <span className="text-sm text-gray-500">
              Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, data.total)} of{' '}
              {data.total} exceptions
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="btn-secondary"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="text-sm text-gray-600">
                Page {page} of {data.pages}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= data.pages}
                className="btn-secondary"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Exception Detail Modal */}
      {selectedExc && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div
              className="fixed inset-0 bg-gray-500 bg-opacity-75"
              onClick={() => setSelectedExc(null)}
            />
            <div className="relative bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
              <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  Exception Details
                </h3>
                <button
                  onClick={() => setSelectedExc(null)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XCircle className="w-6 h-6" />
                </button>
              </div>
              <div className="p-6 space-y-6">
                {/* Exception Info */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-500">Category</label>
                    <p className="text-gray-900 capitalize">
                      {selectedExc.category.replace(/_/g, ' ')}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Priority</label>
                    <span
                      className={clsx(
                        'px-2 py-1 rounded-full text-xs font-medium',
                        priorityConfig[selectedExc.priority].color
                      )}
                    >
                      {priorityConfig[selectedExc.priority].label}
                    </span>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Field</label>
                    <p className="text-gray-900">{selectedExc.field_name}</p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Status</label>
                    <span className={clsx('badge', statusConfig[selectedExc.status].color)}>
                      {statusConfig[selectedExc.status].label}
                    </span>
                  </div>
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-500">Reason</label>
                  <p className="text-gray-900">{selectedExc.reason}</p>
                </div>

                {/* Value Comparison */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-3">Value Comparison</h4>
                  <div className="grid grid-cols-3 gap-4 items-center">
                    <div className="text-center">
                      <p className="text-xs text-gray-500 mb-1">Expected</p>
                      <div className="p-3 bg-success-50 rounded-lg border border-success-200">
                        <p className="font-mono text-success-700">
                          {selectedExc.expected_value || 'N/A'}
                        </p>
                      </div>
                    </div>
                    <div className="flex justify-center">
                      <ArrowRight className="w-5 h-5 text-gray-400" />
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-gray-500 mb-1">Actual</p>
                      <div className="p-3 bg-error-50 rounded-lg border border-error-200">
                        <p className="font-mono text-error-700">
                          {selectedExc.actual_value || 'N/A'}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Document Reference */}
                {selectedExc.document && (
                  <div>
                    <label className="text-sm font-medium text-gray-500">Source Document</label>
                    <div className="flex items-center gap-3 mt-1 p-3 bg-gray-50 rounded-lg">
                      <FileText className="w-5 h-5 text-gray-400" />
                      <div>
                        <p className="text-gray-900">{selectedExc.document.original_filename}</p>
                        <p className="text-sm text-gray-500">
                          {selectedExc.document.doc_type?.replace(/_/g, ' ')}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Resolution Form */}
                {selectedExc.status === 'open' || selectedExc.status === 'in_review' ? (
                  <div className="border-t pt-6 space-y-4">
                    <h4 className="font-medium text-gray-900">Resolve Exception</h4>
                    <div>
                      <label className="text-sm font-medium text-gray-700">
                        Corrected Value (optional)
                      </label>
                      <input
                        type="text"
                        value={correctedValue}
                        onChange={(e) => setCorrectedValue(e.target.value)}
                        className="input mt-1"
                        placeholder="Enter the correct value"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium text-gray-700">
                        Resolution Notes *
                      </label>
                      <textarea
                        value={resolution}
                        onChange={(e) => setResolution(e.target.value)}
                        className="input mt-1"
                        rows={3}
                        placeholder="Explain how this was resolved..."
                      />
                    </div>
                    <div className="flex gap-3">
                      <button
                        onClick={handleResolve}
                        disabled={!resolution.trim() || resolveMutation.isPending}
                        className="btn-primary flex-1"
                      >
                        {resolveMutation.isPending ? 'Resolving...' : 'Resolve Exception'}
                      </button>
                      <button
                        onClick={handleIgnore}
                        disabled={ignoreMutation.isPending}
                        className="btn-secondary"
                      >
                        Ignore
                      </button>
                    </div>
                  </div>
                ) : selectedExc.resolution ? (
                  <div className="border-t pt-6">
                    <h4 className="font-medium text-gray-900 mb-3">Resolution</h4>
                    <div className="bg-success-50 rounded-lg p-4 space-y-2">
                      {selectedExc.resolution.corrected_value && (
                        <div>
                          <span className="text-sm text-gray-500">Corrected Value: </span>
                          <span className="font-mono text-success-700">
                            {selectedExc.resolution.corrected_value}
                          </span>
                        </div>
                      )}
                      <p className="text-gray-700">{selectedExc.resolution.notes}</p>
                      <p className="text-sm text-gray-500">
                        Resolved by {selectedExc.resolved_by} on{' '}
                        {selectedExc.resolved_at && formatDate(selectedExc.resolved_at)}
                      </p>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
