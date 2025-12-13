import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { X, Download, FileSpreadsheet, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import { exportApi } from '../../services/api'

interface ExportTemplate {
  template: string
  name: string
  description: string
  supported_doc_types: string[]
  default_fields: string[]
  available_fields: string[]
}

interface ExportModalProps {
  isOpen: boolean
  onClose: () => void
  documentIds?: string[]
  initialTemplate?: string
}

export default function ExportModal({
  isOpen,
  onClose,
  documentIds = [],
  initialTemplate,
}: ExportModalProps) {
  const [selectedTemplate, setSelectedTemplate] = useState<string>(
    initialTemplate || 'portfolio_financials'
  )
  const [includeRawData, setIncludeRawData] = useState(false)
  const [includeConfidenceScores, setIncludeConfidenceScores] = useState(true)

  const { data: templates, isLoading: loadingTemplates } = useQuery<ExportTemplate[]>({
    queryKey: ['export-templates'],
    queryFn: exportApi.getTemplates,
    enabled: isOpen,
  })

  const exportMutation = useMutation({
    mutationFn: () =>
      exportApi.generateExcel({
        document_ids: documentIds,
        template: selectedTemplate as import('../../types').ExportTemplate,
        format: 'xlsx',
        include_raw_data: includeRawData,
        include_confidence_scores: includeConfidenceScores,
      }),
    onSuccess: (data) => {
      toast.success('Export generated successfully!')
      // Open download link in new tab
      if (data.download_url) {
        window.open(data.download_url, '_blank')
      }
      onClose()
    },
    onError: (error: Error) => {
      toast.error(`Export failed: ${error.message}`)
    },
  })

  const bulkExportMutation = useMutation({
    mutationFn: () =>
      exportApi.generateBulk({
        template: selectedTemplate,
      }),
    onSuccess: (data) => {
      toast.success('Bulk export generated successfully!')
      if (data.download_url) {
        window.open(data.download_url, '_blank')
      }
      onClose()
    },
    onError: (error: Error) => {
      toast.error(`Export failed: ${error.message}`)
    },
  })

  const handleExport = () => {
    if (documentIds.length > 0) {
      exportMutation.mutate()
    } else {
      bulkExportMutation.mutate()
    }
  }

  const isExporting = exportMutation.isPending || bulkExportMutation.isPending

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-30 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex items-center gap-3">
              <FileSpreadsheet className="w-6 h-6 text-indigo-600" />
              <h2 className="text-lg font-semibold text-gray-900">Export to Excel</h2>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content */}
          <div className="p-4 space-y-4">
            {/* Document count */}
            <div className="bg-indigo-50 text-indigo-700 px-4 py-3 rounded-lg">
              {documentIds.length > 0 ? (
                <p className="text-sm">
                  Exporting <strong>{documentIds.length}</strong> selected document(s)
                </p>
              ) : (
                <p className="text-sm">
                  Exporting <strong>all processed documents</strong>
                </p>
              )}
            </div>

            {/* Template selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Export Template
              </label>
              {loadingTemplates ? (
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading templates...
                </div>
              ) : (
                <div className="space-y-2">
                  {templates?.map((template) => (
                    <label
                      key={template.template}
                      className={clsx(
                        'flex items-start p-3 border rounded-lg cursor-pointer transition-colors',
                        selectedTemplate === template.template
                          ? 'border-indigo-500 bg-indigo-50'
                          : 'border-gray-200 hover:border-gray-300'
                      )}
                    >
                      <input
                        type="radio"
                        name="template"
                        value={template.template}
                        checked={selectedTemplate === template.template}
                        onChange={(e) => setSelectedTemplate(e.target.value)}
                        className="mt-1 text-indigo-600 focus:ring-indigo-500"
                      />
                      <div className="ml-3">
                        <p className="font-medium text-gray-900">{template.name}</p>
                        <p className="text-sm text-gray-500">{template.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Options */}
            <div className="space-y-3">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={includeConfidenceScores}
                  onChange={(e) => setIncludeConfidenceScores(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-gray-700">
                  Include confidence scores
                </span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={includeRawData}
                  onChange={(e) => setIncludeRawData(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-gray-700">
                  Include raw extracted data
                </span>
              </label>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-4 border-t bg-gray-50">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              disabled={isExporting}
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={isExporting || !selectedTemplate}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  Export
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
