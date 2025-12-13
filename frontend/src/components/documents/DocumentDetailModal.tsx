import { useState, useEffect } from 'react'
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  X,
  CheckCircle,
  AlertTriangle,
  Edit2,
  Save,
  RotateCcw,
  FileText,
  Clock,
  Zap,
  Download,
  RefreshCw,
} from 'lucide-react'
import clsx from 'clsx'
import { documentsApi, exceptionsApi } from '../../services/api'
import type { Document, Exception } from '../../types'

interface DocumentDetailModalProps {
  document: Document
  onClose: () => void
}

export default function DocumentDetailModal({ document, onClose }: DocumentDetailModalProps) {
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [editedData, setEditedData] = useState<Record<string, unknown>>({})

  // Load related exceptions
  const { data: exceptionsData } = useQuery({
    queryKey: ['document-exceptions', document.id],
    queryFn: () => exceptionsApi.list({ document_id: document.id, page_size: 10 }),
  })

  useEffect(() => {
    if (document.extracted_data) {
      setEditedData(document.extracted_data)
    }
  }, [document.extracted_data])

  const updateMutation = useMutation({
    mutationFn: (updates: Partial<Document>) => documentsApi.update(document.id, updates),
    onSuccess: () => {
      toast.success('Document updated successfully')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      setIsEditing(false)
    },
    onError: (error: Error) => {
      toast.error(`Update failed: ${error.message}`)
    },
  })

  const reprocessMutation = useMutation({
    mutationFn: () => documentsApi.reprocess(document.id),
    onSuccess: () => {
      toast.success('Document queued for reprocessing')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (error: Error) => {
      toast.error(`Reprocess failed: ${error.message}`)
    },
  })

  const handleSave = () => {
    updateMutation.mutate({ extracted_data: editedData })
  }

  const handleFieldChange = (key: string, value: string) => {
    setEditedData((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.85) return 'text-success-600 bg-success-50'
    if (confidence >= 0.7) return 'text-warning-600 bg-warning-50'
    return 'text-error-600 bg-error-50'
  }

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return '-'
    if (typeof value === 'object') return JSON.stringify(value)
    return String(value)
  }

  const extractedFields = document.extracted_data
    ? Object.entries(document.extracted_data).filter(([key]) => !key.startsWith('_'))
    : []

  const fieldConfidences = document.field_confidences || {}

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75"
          onClick={onClose}
        />
        <div className="relative bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between z-10">
            <div className="flex items-center gap-3">
              <FileText className="w-6 h-6 text-gray-400" />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  Document Details
                </h3>
                <p className="text-sm text-gray-500 truncate max-w-md">
                  {document.original_filename}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Status Banner */}
            <div className={clsx(
              'flex items-center justify-between p-4 rounded-lg',
              document.status === 'processed' && 'bg-success-50 border border-success-200',
              document.status === 'needs_review' && 'bg-warning-50 border border-warning-200',
              document.status === 'failed' && 'bg-error-50 border border-error-200',
              document.status === 'pending' && 'bg-gray-50 border border-gray-200',
              document.status === 'processing' && 'bg-primary-50 border border-primary-200',
            )}>
              <div className="flex items-center gap-3">
                {document.status === 'processed' && <CheckCircle className="w-5 h-5 text-success-600" />}
                {document.status === 'needs_review' && <AlertTriangle className="w-5 h-5 text-warning-600" />}
                {document.status === 'failed' && <X className="w-5 h-5 text-error-600" />}
                {document.status === 'pending' && <Clock className="w-5 h-5 text-gray-600" />}
                {document.status === 'processing' && <RefreshCw className="w-5 h-5 text-primary-600 animate-spin" />}
                <div>
                  <p className="font-medium capitalize">
                    {document.status.replace(/_/g, ' ')}
                  </p>
                  {document.processing_error && (
                    <p className="text-sm text-error-600">{document.processing_error}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => reprocessMutation.mutate()}
                  disabled={document.status === 'processing'}
                  className="btn-secondary text-sm"
                >
                  <RefreshCw className="w-4 h-4 mr-1" />
                  Reprocess
                </button>
              </div>
            </div>

            {/* Document Info Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="card p-4">
                <p className="text-xs font-medium text-gray-500 uppercase">Type</p>
                <p className="text-sm font-semibold text-gray-900 mt-1">
                  {document.doc_type?.replace(/_/g, ' ') || 'Unknown'}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs font-medium text-gray-500 uppercase">Confidence</p>
                <p className={clsx(
                  'text-sm font-semibold mt-1',
                  document.confidence && document.confidence >= 0.85 ? 'text-success-600' :
                  document.confidence && document.confidence >= 0.7 ? 'text-warning-600' :
                  'text-error-600'
                )}>
                  {document.confidence ? `${(document.confidence * 100).toFixed(1)}%` : '-'}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs font-medium text-gray-500 uppercase">Processor</p>
                <p className="text-sm font-semibold text-gray-900 mt-1">
                  {document.processor_used?.replace(/_/g, ' ') || '-'}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs font-medium text-gray-500 uppercase">Processing Time</p>
                <p className="text-sm font-semibold text-gray-900 mt-1">
                  {document.processing_time_ms ? `${document.processing_time_ms}ms` : '-'}
                </p>
              </div>
            </div>

            {/* Extracted Fields */}
            {extractedFields.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-md font-semibold text-gray-900">Extracted Fields</h4>
                  <div className="flex items-center gap-2">
                    {isEditing ? (
                      <>
                        <button
                          onClick={() => {
                            setEditedData(document.extracted_data || {})
                            setIsEditing(false)
                          }}
                          className="btn-secondary text-sm"
                        >
                          <RotateCcw className="w-4 h-4 mr-1" />
                          Cancel
                        </button>
                        <button
                          onClick={handleSave}
                          disabled={updateMutation.isPending}
                          className="btn-primary text-sm"
                        >
                          <Save className="w-4 h-4 mr-1" />
                          Save Changes
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="btn-secondary text-sm"
                      >
                        <Edit2 className="w-4 h-4 mr-1" />
                        Edit Fields
                      </button>
                    )}
                  </div>
                </div>

                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-gray-50 border-b">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Field
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Value
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase w-24">
                          Confidence
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {extractedFields.map(([key, value]) => {
                        const confidence = fieldConfidences[key]
                        return (
                          <tr key={key} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">
                              {key.replace(/_/g, ' ')}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {isEditing ? (
                                <input
                                  type="text"
                                  value={formatValue(editedData[key])}
                                  onChange={(e) => handleFieldChange(key, e.target.value)}
                                  className="input w-full"
                                />
                              ) : (
                                <span className="font-mono">{formatValue(value)}</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-center">
                              {confidence !== undefined ? (
                                <span className={clsx(
                                  'inline-flex items-center px-2 py-1 rounded text-xs font-medium',
                                  getConfidenceColor(confidence)
                                )}>
                                  {(confidence * 100).toFixed(0)}%
                                </span>
                              ) : (
                                <span className="text-gray-400">-</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Related Exceptions */}
            {exceptionsData && exceptionsData.items.length > 0 && (
              <div>
                <h4 className="text-md font-semibold text-gray-900 mb-4">
                  Related Exceptions ({exceptionsData.total})
                </h4>
                <div className="space-y-2">
                  {exceptionsData.items.map((exception: Exception) => (
                    <div
                      key={exception.id}
                      className={clsx(
                        'p-4 rounded-lg border',
                        exception.status === 'open' && 'border-error-200 bg-error-50',
                        exception.status === 'resolved' && 'border-success-200 bg-success-50',
                        exception.status === 'ignored' && 'border-gray-200 bg-gray-50',
                      )}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium text-gray-900">
                            {exception.field_name ? `${exception.field_name}: ` : ''}
                            {exception.reason}
                          </p>
                          <p className="text-sm text-gray-500 mt-1">
                            Category: {exception.category.replace(/_/g, ' ')} |
                            Priority: {exception.priority}
                          </p>
                        </div>
                        <span className={clsx(
                          'badge',
                          exception.status === 'open' && 'badge-error',
                          exception.status === 'resolved' && 'badge-success',
                          exception.status === 'ignored' && 'badge-gray',
                        )}>
                          {exception.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Timestamps */}
            <div className="grid grid-cols-2 gap-4 text-sm text-gray-500">
              <div>
                <span className="font-medium">Uploaded:</span>{' '}
                {new Date(document.created_at).toLocaleString()}
              </div>
              {document.processed_at && (
                <div>
                  <span className="font-medium">Processed:</span>{' '}
                  {new Date(document.processed_at).toLocaleString()}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 border-t px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Zap className="w-4 h-4" />
              Processing: {document.processor_used?.replace(/_/g, ' ') || 'N/A'}
            </div>
            <div className="flex items-center gap-2">
              <button className="btn-secondary" onClick={onClose}>
                Close
              </button>
              {document.status === 'needs_review' && (
                <button
                  onClick={() => updateMutation.mutate({ status: 'processed' as const })}
                  disabled={updateMutation.isPending}
                  className="btn-primary"
                >
                  <CheckCircle className="w-4 h-4 mr-1" />
                  Approve
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
